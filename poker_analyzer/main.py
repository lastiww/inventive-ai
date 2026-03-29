"""Poker Stream GTO Analyzer — Main pipeline.

Usage:
    python -m poker_analyzer.main --device 0 --site winamax
    python -m poker_analyzer.main --device 1 --site coinpoker --debug

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
from poker_analyzer.ocr.table_parser import TableParser
from poker_analyzer.solver.exploitative import ExploitativeSolver
from poker_analyzer.solver.player_tracker import PlayerTracker
from poker_analyzer.solver.range_manager import RangeManager
from poker_analyzer.solver.texas_solver import TexasSolver


class PokerAnalyzer:
    """Main application — orchestrates capture → OCR → solver → display."""

    def __init__(self, config: Config):
        self.config = config

        # Modules
        self.capture = VideoCapture(config.capture, config.window)
        self.parser = TableParser(config)
        self.solver = TexasSolver(config.solver)
        self.range_manager = RangeManager()
        self.tracker = PlayerTracker()
        self.exploit_solver = ExploitativeSolver(config.solver, self.tracker)
        self.overlay = OverlayDisplay(config.window)

        # State
        self._last_board_str = ""
        self._last_pot = 0.0
        self._show_exploit = True

    def run(self):
        """Main loop."""
        # Open capture device
        if not self.capture.open():
            print("[ERROR] Failed to open capture device. Check device ID.")
            return

        # Build overlay window
        self.overlay.build()

        print("[READY] Poker GTO Analyzer running.")
        print("  D = Debug OCR | Q = Quit")
        print(f"  Site: {self.config.site}")
        print(f"  Capture device: {self.config.capture.device_id}")

        try:
            self._main_loop()
        except KeyboardInterrupt:
            print("\n[QUIT] Interrupted.")
        finally:
            self.capture.release()
            self.overlay.destroy()

    def _main_loop(self):
        """Continuous frame processing loop."""
        frame_interval = 1.0 / 10  # Process at 10 FPS (OCR doesn't need 30fps)
        solve_cooldown = 2.0  # Don't re-solve more often than every 2s
        last_solve_time = 0.0

        while True:
            loop_start = time.time()

            # Read frame
            frame = self.capture.read_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            # Parse game state via OCR
            game_state = self.parser.parse_frame(frame)

            # Update debug ROIs on capture window
            if self.config.debug_ocr:
                debug_rois = self.parser.get_debug_rois(frame)
                self.capture.set_debug_rois(debug_rois)

            # Check if game state changed (new board / pot change)
            state_changed = self._detect_state_change(game_state)

            # Solve if state changed and enough time passed
            now = time.time()
            if state_changed and (now - last_solve_time) > solve_cooldown:
                self._trigger_solve(game_state)
                last_solve_time = now

            # Get solver results
            gto_result = self.solver.get_result()
            exploit_result = None

            if self._show_exploit and gto_result:
                # Find opponent to exploit
                opponent = self._find_opponent(game_state)
                if opponent:
                    exploit_result = game_state.exploitative_result

            # Update overlay
            opponent_stats = None
            opponent = self._find_opponent(game_state)
            if opponent:
                opponent_stats = self.tracker.get_stats(opponent)

            self.overlay.update(
                game_state=game_state,
                gto_result=gto_result,
                exploit_result=exploit_result,
                opponent_stats=opponent_stats,
                is_solving=self.solver.is_solving(),
            )

            # Show capture frame
            self.capture.show_frame(frame)

            # Process overlay events
            self.overlay.process_events()

            # Handle keyboard
            key = cv2.waitKey(1) & 0xFF
            action = self.capture.handle_key(key)

            if action == "quit":
                break
            elif action == "toggle_debug":
                self.config.debug_ocr = not self.config.debug_ocr
                self.capture.set_debug_mode(self.config.debug_ocr)
            elif key == ord('e') or key == ord('E'):
                self._show_exploit = not self._show_exploit
                mode = "Exploitative + GTO" if self._show_exploit else "GTO Only"
                self.overlay.set_status(f"Mode: {mode}")
                print(f"[MODE] {mode}")

            # Frame rate control
            elapsed = time.time() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _detect_state_change(self, state: GameState) -> bool:
        """Detect if the game state has meaningfully changed."""
        board_str = state.board_str
        pot = state.pot_bb

        changed = (board_str != self._last_board_str) or (abs(pot - self._last_pot) > 0.5)

        self._last_board_str = board_str
        self._last_pot = pot

        return changed

    def _trigger_solve(self, state: GameState):
        """Trigger solver for the current game state."""
        if state.street == Street.PREFLOP:
            # Preflop: instant lookup
            result = self.solver.solve(state, "", "")
            state.gto_result = result
            return

        # Postflop: need ranges based on positions
        hero = state.hero
        if hero is None or hero.position is None:
            return

        # Find villain position (first active non-hero player)
        villain = None
        for p in state.active_players:
            if p != hero and p.position is not None:
                villain = p
                break

        if villain is None:
            return

        # Determine OOP/IP
        oop_pos, ip_pos = self._determine_oop_ip(hero, villain)
        is_3bet = state.pot_bb > 12  # rough heuristic for 3bet pot

        oop_range, ip_range = self.range_manager.get_ranges_for_spot(
            oop_pos, ip_pos, is_3bet_pot=is_3bet
        )

        # Solve GTO (async)
        self.solver.solve_async(state, oop_range, ip_range)

        # Solve exploitative if we have stats
        if villain and self._show_exploit:
            exploit_result = self.exploit_solver.solve_exploitative(
                state, villain.name, oop_range, ip_range
            )
            state.exploitative_result = exploit_result

    def _find_opponent(self, state: GameState) -> str | None:
        """Find the main opponent's name."""
        hero = state.hero
        if hero is None:
            return None

        for p in state.active_players:
            if p != hero and p.is_active:
                return p.name
        return None

    def _determine_oop_ip(self, player1, player2):
        """Determine who is OOP and IP based on positions."""
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

        # Lower index = earlier to act = OOP
        if idx1 < idx2:
            return pos1, pos2
        else:
            return pos2, pos1


def parse_args():
    parser = argparse.ArgumentParser(description="Poker Stream GTO Analyzer")
    parser.add_argument(
        "--device", type=int, default=0,
        help="Capture card device ID (default: 0)",
    )
    parser.add_argument(
        "--site", choices=["winamax", "coinpoker"], default="winamax",
        help="Poker site to analyze (default: winamax)",
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
        "--overlay-x", type=int, default=1920,
        help="Overlay window X position (default: 1920 = second monitor)",
    )
    parser.add_argument(
        "--overlay-y", type=int, default=0,
        help="Overlay window Y position",
    )
    parser.add_argument(
        "--capture-x", type=int, default=0,
        help="Capture preview window X position",
    )
    parser.add_argument(
        "--capture-y", type=int, default=0,
        help="Capture preview window Y position",
    )
    parser.add_argument(
        "--width", type=int, default=960,
        help="Window width for both windows",
    )
    parser.add_argument(
        "--height", type=int, default=540,
        help="Window height for both windows",
    )
    parser.add_argument(
        "--rendercolor-x", type=int, default=1920,
        help="RenderColorQC window X position (default: 1920 = second monitor)",
    )
    parser.add_argument(
        "--rendercolor-y", type=int, default=0,
        help="RenderColorQC window Y position",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    config = Config(
        site=args.site,
        debug_ocr=args.debug,
    )

    # Apply CLI args
    config.capture.device_id = args.device
    config.capture.rendercolor_x = args.rendercolor_x
    config.capture.rendercolor_y = args.rendercolor_y
    config.solver.binary_path = args.solver_path

    config.window.capture_x = args.capture_x
    config.window.capture_y = args.capture_y
    config.window.capture_width = args.width
    config.window.capture_height = args.height

    config.window.overlay_x = args.overlay_x
    config.window.overlay_y = args.overlay_y
    config.window.overlay_width = args.width
    config.window.overlay_height = args.height

    print("=" * 50)
    print("  POKER STREAM GTO ANALYZER")
    print("=" * 50)
    print(f"  Site:    {config.site}")
    print(f"  Solver:  {config.solver.binary_path}")
    print(f"  Debug:   {config.debug_ocr}")
    print(f"  RenderColorQC: ({config.capture.rendercolor_x}, {config.capture.rendercolor_y})")
    print(f"  Capture: ({config.window.capture_x}, {config.window.capture_y})")
    print(f"  Overlay: ({config.window.overlay_x}, {config.window.overlay_y})")
    print(f"  Size:    {config.window.capture_width}x{config.window.capture_height}")
    print("=" * 50)

    analyzer = PokerAnalyzer(config)
    analyzer.run()


if __name__ == "__main__":
    main()
