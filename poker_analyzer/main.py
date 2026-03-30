"""Poker Stream GTO Analyzer — Main pipeline with multi-table support.

Usage:
    python -m poker_analyzer.main --site coinpoker --rendercolor-x 1920
    python -m poker_analyzer.main --site coinpoker --tables 2x3 --rendercolor-x 1920
    python -m poker_analyzer.main --site winamax --tables 2x2 --debug

Keys:
    D — Toggle debug OCR rectangles
    E — Toggle exploitative mode
    Q / ESC — Quit
"""

import argparse
import time

import cv2

from poker_analyzer.capture.video_capture import VideoCapture
from poker_analyzer.config import Config
from poker_analyzer.display.overlay import OverlayDisplay
from poker_analyzer.models.game_state import GameState, Street
from poker_analyzer.multi_table import MultiTableManager
from poker_analyzer.solver.range_manager import RangeManager


class PokerAnalyzer:
    """Main application — orchestrates capture → OCR → solver → display.

    Supports multi-table: splits the captured frame into a grid and
    analyzes each table independently.
    """

    def __init__(self, config: Config, table_cols: int = 1, table_rows: int = 1):
        self.config = config
        self.capture = VideoCapture(config.capture, config.window)
        self.overlay = OverlayDisplay()
        self.multi = MultiTableManager(config, table_cols, table_rows)
        self._show_exploit = True

    def run(self):
        """Main loop."""
        if not self.capture.open():
            print("[ERROR] Failed to open capture device.")
            return

        window_name = "Poker GTO Analyzer"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(
            window_name,
            self.config.window.overlay_width,
            self.config.window.overlay_height,
        )
        cv2.moveWindow(
            window_name,
            self.config.window.overlay_x,
            self.config.window.overlay_y,
        )

        print("[READY] Poker GTO Analyzer running.")
        print(f"  Tables: {self.multi.cols}x{self.multi.rows} ({self.multi.num_tables} tables)")
        print(f"  Site: {self.config.site}")
        print("  D = Debug OCR | E = Toggle Exploit | Q = Quit")

        try:
            self._main_loop(window_name)
        except KeyboardInterrupt:
            print("\n[QUIT] Interrupted.")
        finally:
            self.capture.release()
            cv2.destroyAllWindows()

    def _main_loop(self, window_name: str):
        """Continuous frame processing loop."""
        frame_interval = 1.0 / 10  # 10 FPS
        solve_cooldown = 2.0

        while True:
            loop_start = time.time()

            # Capture full frame from RenderColorQC
            frame = self.capture.read_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            fh, fw = frame.shape[:2]
            display = frame.copy()

            # Split frame into table sub-frames
            table_frames = self.multi.split_frame(frame)

            # Process each table
            all_debug_rois = []
            all_labels = []

            for idx, (sub_frame, off_x, off_y, tw, th) in enumerate(table_frames):
                table = self.multi.tables[idx]

                # Parse game state via OCR
                table.game_state = table.parser.parse_frame(sub_frame)

                # Debug ROIs
                if self.config.debug_ocr:
                    rois = self.multi.get_debug_rois_for_table(table, sub_frame, off_x, off_y)
                    all_debug_rois.extend(rois)

                # Check state change and solve
                now = time.time()
                state_changed = self._detect_state_change(table)
                if state_changed and (now - table.last_solve_time) > solve_cooldown:
                    self._trigger_solve(table)
                    table.last_solve_time = now

                # Get results
                table.gto_result = table.solver.get_result()
                if self._show_exploit and table.gto_result and table.game_state:
                    opponent = self._find_opponent(table.game_state)
                    if opponent:
                        table.exploit_result = table.game_state.exploitative_result

                # Get label anchors for this table (converted to full-frame coords)
                if table.gto_result or table.exploit_result:
                    anchors = self.multi.get_label_anchors_for_table(
                        idx, off_x, off_y, tw, th, fw, fh,
                    )
                    all_labels.append((anchors, table))

            # Draw all overlays on the full frame
            display = self.overlay.draw_overlay(
                frame=frame,
                game_state=None,
                gto_result=None,
                exploit_result=None,
                is_solving=any(t.solver.is_solving() for t in self.multi.tables),
                debug_rois=all_debug_rois if all_debug_rois else None,
                player_label_anchors=None,
            )

            # Draw per-table player labels
            for anchors, table in all_labels:
                self.overlay.draw_player_labels_direct(
                    display, fw, fh, anchors,
                    table.game_state,
                    table.gto_result,
                    table.exploit_result,
                )

            cv2.imshow(window_name, display)

            # Keyboard
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == ord('Q') or key == 27:
                break
            elif key == ord('d') or key == ord('D'):
                self.config.debug_ocr = not self.config.debug_ocr
                mode = "ON" if self.config.debug_ocr else "OFF"
                self.overlay.set_status(f"Debug OCR: {mode}")
                print(f"[DEBUG] OCR rectangles {mode}")
            elif key == ord('e') or key == ord('E'):
                self._show_exploit = not self._show_exploit
                mode = "EXP + GTO" if self._show_exploit else "GTO Only"
                self.overlay.set_status(f"Mode: {mode}")
                print(f"[MODE] {mode}")

            # Frame rate control
            elapsed = time.time() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _detect_state_change(self, table) -> bool:
        """Detect if a table's state has changed."""
        state = table.game_state
        if state is None:
            return False

        board_str = state.board_str
        pot = state.pot_bb
        changed = (board_str != table.last_board_str) or (abs(pot - table.last_pot) > 0.5)
        table.last_board_str = board_str
        table.last_pot = pot
        return changed

    def _trigger_solve(self, table):
        """Trigger solver for a specific table."""
        state = table.game_state
        if state is None:
            return

        if state.street == Street.PREFLOP:
            result = table.solver.solve(state, "", "")
            state.gto_result = result
            return

        hero = state.hero
        if hero is None or hero.position is None:
            return

        villain = None
        for p in state.active_players:
            if p != hero and p.position is not None:
                villain = p
                break
        if villain is None:
            return

        oop_pos, ip_pos = self._determine_oop_ip(hero, villain)
        is_3bet = state.pot_bb > 12
        oop_range, ip_range = table.range_manager.get_ranges_for_spot(
            oop_pos, ip_pos, is_3bet_pot=is_3bet,
        )
        table.solver.solve_async(state, oop_range, ip_range)

        if self._show_exploit:
            exploit_result = table.exploit_solver.solve_exploitative(
                state, villain.name, oop_range, ip_range,
            )
            state.exploitative_result = exploit_result

    def _find_opponent(self, state: GameState) -> str | None:
        hero = state.hero
        if hero is None:
            return None
        for p in state.active_players:
            if p != hero and p.is_active:
                return p.name
        return None

    def _determine_oop_ip(self, player1, player2):
        from poker_analyzer.models.game_state import Position
        position_order = [
            Position.SB, Position.BB, Position.UTG,
            Position.MP, Position.CO, Position.BTN,
        ]
        pos1 = player1.position
        pos2 = player2.position
        if pos1 is None or pos2 is None:
            return pos1 or Position.BB, pos2 or Position.CO
        idx1 = position_order.index(pos1) if pos1 in position_order else 0
        idx2 = position_order.index(pos2) if pos2 in position_order else 0
        if idx1 < idx2:
            return pos1, pos2
        return pos2, pos1


def parse_args():
    parser = argparse.ArgumentParser(description="Poker Stream GTO Analyzer")
    parser.add_argument(
        "--device", type=int, default=0,
        help="Capture card device ID (default: 0)",
    )
    parser.add_argument(
        "--site", choices=["winamax", "coinpoker"], default="winamax",
        help="Poker site (default: winamax)",
    )
    parser.add_argument(
        "--tables", type=str, default="1x1",
        help="Table layout: COLSxROWS (e.g., 1x1, 2x2, 2x3, 3x2). Default: 1x1",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Start with debug OCR rectangles enabled",
    )
    parser.add_argument(
        "--solver-path", type=str, default="./TexasSolver",
        help="Path to TexasSolver binary",
    )
    parser.add_argument(
        "--rendercolor-x", type=int, default=1920,
        help="RenderColorQC window X position (default: 1920)",
    )
    parser.add_argument(
        "--rendercolor-y", type=int, default=0,
        help="RenderColorQC window Y position",
    )
    parser.add_argument(
        "--overlay-x", type=int, default=1920,
        help="Output window X position (default: 1920)",
    )
    parser.add_argument(
        "--overlay-y", type=int, default=0,
        help="Output window Y position",
    )
    parser.add_argument(
        "--width", type=int, default=1920,
        help="Window width (default: 1920)",
    )
    parser.add_argument(
        "--height", type=int, default=1080,
        help="Window height (default: 1080)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Parse table grid
    try:
        cols, rows = args.tables.lower().split("x")
        cols, rows = int(cols), int(rows)
    except ValueError:
        print(f"[ERROR] Invalid --tables format '{args.tables}'. Use COLSxROWS (e.g., 2x3)")
        return

    config = Config(site=args.site, debug_ocr=args.debug)
    config.capture.device_id = args.device
    config.capture.rendercolor_x = args.rendercolor_x
    config.capture.rendercolor_y = args.rendercolor_y
    config.solver.binary_path = args.solver_path
    config.window.overlay_x = args.overlay_x
    config.window.overlay_y = args.overlay_y
    config.window.overlay_width = args.width
    config.window.overlay_height = args.height

    num_tables = cols * rows

    print("=" * 50)
    print("  POKER STREAM GTO ANALYZER")
    print("=" * 50)
    print(f"  Site:          {config.site}")
    print(f"  Tables:        {cols}x{rows} = {num_tables} tables")
    print(f"  Solver:        {config.solver.binary_path}")
    print(f"  Debug:         {config.debug_ocr}")
    print(f"  RenderColorQC: ({config.capture.rendercolor_x}, {config.capture.rendercolor_y})")
    print(f"  Output:        ({config.window.overlay_x}, {config.window.overlay_y})")
    print(f"  Size:          {args.width}x{args.height}")
    print("=" * 50)

    analyzer = PokerAnalyzer(config, cols, rows)
    analyzer.run()


if __name__ == "__main__":
    main()
