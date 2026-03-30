"""Poker Stream GTO Analyzer — Main pipeline.

Captures the screen region where RenderColorQC renders the stream,
analyzes each detected poker table, and draws overlay labels.
"""

import argparse
import time

import cv2
import numpy as np

from poker_analyzer.capture.video_capture import VideoCapture
from poker_analyzer.config import Config
from poker_analyzer.display.overlay import OverlayDisplay
from poker_analyzer.models.game_state import GameState, Street
from poker_analyzer.multi_table import MultiTableManager


class PokerAnalyzer:
    """Main application — capture → OCR → solver → overlay."""

    def __init__(self, config: Config, table_cols: int = 1, table_rows: int = 1):
        self.config = config
        self.capture = VideoCapture(config.capture, config.window)
        self.overlay = OverlayDisplay()
        self.multi = MultiTableManager(config, table_cols, table_rows)
        self._show_exploit = True
        self._stop_flag = False

    def run(self):
        """Main loop."""
        if not self.capture.open():
            print("[ERROR] Failed to open capture.")
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

        print("[READY] Analyzer running.")

        try:
            self._main_loop(window_name)
        except KeyboardInterrupt:
            pass
        finally:
            self.capture.release()
            cv2.destroyAllWindows()

    def _main_loop(self, window_name: str):
        frame_interval = 1.0 / 10  # 10 FPS
        solve_cooldown = 2.0

        while not self._stop_flag:
            loop_start = time.time()

            frame = self.capture.read_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            fh, fw = frame.shape[:2]

            # Split into tables
            table_frames = self.multi.split_frame(frame)

            all_debug_rois = []
            all_labels = []

            for idx, (sub_frame, off_x, off_y, tw, th) in enumerate(table_frames):
                table = self.multi.tables[idx]

                # Parse game state
                table.game_state = table.parser.parse_frame(sub_frame)

                # Debug ROIs
                if self.config.debug_ocr:
                    rois = self.multi.get_debug_rois_for_table(table, sub_frame, off_x, off_y)
                    all_debug_rois.extend(rois)

                # Solve if state changed
                now = time.time()
                if self._detect_state_change(table) and (now - table.last_solve_time) > solve_cooldown:
                    self._trigger_solve(table)
                    table.last_solve_time = now

                # Get results
                table.gto_result = table.solver.get_result()
                if self._show_exploit and table.gto_result and table.game_state:
                    opponent = self._find_opponent(table.game_state)
                    if opponent:
                        table.exploit_result = table.game_state.exploitative_result

                # Anchors
                if table.gto_result or table.exploit_result:
                    anchors = self.multi.get_label_anchors_for_table(
                        idx, off_x, off_y, tw, th, fw, fh,
                    )
                    all_labels.append((anchors, table))

            # Draw overlay
            display = self.overlay.draw_overlay(
                frame=frame,
                debug_rois=all_debug_rois if all_debug_rois else None,
                is_solving=any(t.solver.is_solving() for t in self.multi.tables),
            )

            for anchors, table in all_labels:
                self.overlay.draw_player_labels_direct(
                    display, fw, fh, anchors,
                    table.game_state, table.gto_result, table.exploit_result,
                )

            cv2.imshow(window_name, display)

            # Keyboard (also works from OpenCV window)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == ord('Q') or key == 27:
                break
            elif key == ord('d') or key == ord('D'):
                self.config.debug_ocr = not self.config.debug_ocr
            elif key == ord('e') or key == ord('E'):
                self._show_exploit = not self._show_exploit

            elapsed = time.time() - loop_start
            if frame_interval - elapsed > 0:
                time.sleep(frame_interval - elapsed)

    def _detect_state_change(self, table) -> bool:
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

        from poker_analyzer.models.game_state import Position
        position_order = [
            Position.SB, Position.BB, Position.UTG,
            Position.MP, Position.CO, Position.BTN,
        ]
        pos1, pos2 = hero.position, villain.position
        if pos1 and pos2:
            i1 = position_order.index(pos1) if pos1 in position_order else 0
            i2 = position_order.index(pos2) if pos2 in position_order else 0
            oop, ip = (pos1, pos2) if i1 < i2 else (pos2, pos1)
        else:
            oop, ip = Position.BB, Position.CO

        is_3bet = state.pot_bb > 12
        oop_range, ip_range = table.range_manager.get_ranges_for_spot(oop, ip, is_3bet_pot=is_3bet)
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


def parse_args():
    parser = argparse.ArgumentParser(description="Poker Stream GTO Analyzer")
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--site", choices=["winamax", "coinpoker"], default="winamax")
    parser.add_argument("--tables", type=str, default="1x1")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--solver-path", type=str, default="./TexasSolver")
    parser.add_argument("--rendercolor-x", type=int, default=1920)
    parser.add_argument("--rendercolor-y", type=int, default=0)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        cols, rows = args.tables.lower().split("x")
        cols, rows = int(cols), int(rows)
    except ValueError:
        cols, rows = 1, 1

    config = Config(site=args.site, debug_ocr=args.debug)
    config.capture.device_id = args.device
    config.capture.rendercolor_x = args.rendercolor_x
    config.capture.rendercolor_y = args.rendercolor_y
    config.capture.width = args.width
    config.capture.height = args.height
    config.solver.binary_path = args.solver_path
    config.window.overlay_x = args.rendercolor_x
    config.window.overlay_y = args.rendercolor_y
    config.window.overlay_width = args.width
    config.window.overlay_height = args.height

    print("=" * 50)
    print("  POKER GTO ANALYZER")
    print("=" * 50)
    print(f"  Site:     {config.site}")
    print(f"  Tables:   {cols}x{rows}")
    print(f"  Capture:  ({config.capture.rendercolor_x}, {config.capture.rendercolor_y})")
    print(f"  Size:     {args.width}x{args.height}")
    print("=" * 50)

    analyzer = PokerAnalyzer(config, cols, rows)
    analyzer.run()


if __name__ == "__main__":
    main()
