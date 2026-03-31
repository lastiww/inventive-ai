"""Poker Stream GTO Analyzer — Main pipeline.

Reads the screen region where RenderColorQC renders (for OCR),
auto-detects poker tables, and draws transparent overlay labels.
"""

import time

from poker_analyzer.capture.video_capture import VideoCapture
from poker_analyzer.config import Config
from poker_analyzer.display.overlay import OverlayDisplay
from poker_analyzer.models.game_state import GameState, Street
from poker_analyzer.multi_table import MultiTableManager


class PokerAnalyzer:
    """Main application — OCR analysis + transparent overlay."""

    def __init__(self, config: Config):
        self.config = config
        self.capture = VideoCapture(config.capture, config.window)
        self.multi = MultiTableManager(config)
        self._show_exploit = True
        self._stop_flag = False
        self._overlay: OverlayDisplay | None = None

    def run(self):
        """Main loop (used in CLI mode)."""
        if not self.capture.open():
            return

        self._overlay = OverlayDisplay(
            x=self.config.window.overlay_x,
            y=self.config.window.overlay_y,
            width=self.config.window.overlay_width,
            height=self.config.window.overlay_height,
        )
        self._overlay.build()

        print("[READY] Overlay active.")

        try:
            while not self._stop_flag:
                frame = self.capture.read_frame()
                if frame is None:
                    self._overlay.process_events()
                    time.sleep(0.1)
                    continue

                fh, fw = frame.shape[:2]
                detected = self.multi.update_tables(frame)

                for sub_frame, table in detected:
                    table.game_state = table.parser.parse_frame(sub_frame)

                    if self._detect_state_change(table):
                        now = time.time()
                        if (now - table.last_solve_time) > 2.0:
                            self._trigger_solve(table)
                            table.last_solve_time = now

                    table.gto_result = table.solver.get_result()
                    if self._show_exploit and table.gto_result and table.game_state:
                        opponent = self._find_opponent(table.game_state)
                        if opponent:
                            table.exploit_result = table.game_state.exploitative_result

                    if self._overlay:
                        anchors = self.multi.get_label_anchors_for_table(table, fw, fh)
                        self._overlay.update_labels(
                            anchors, table.game_state,
                            table.gto_result,
                            table.exploit_result if self._show_exploit else None,
                        )

                if self._overlay:
                    self._overlay.process_events()

                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self.capture.release()
            if self._overlay:
                self._overlay.destroy()

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
        order = [Position.SB, Position.BB, Position.UTG, Position.MP, Position.CO, Position.BTN]
        pos1, pos2 = hero.position, villain.position
        if pos1 and pos2:
            i1 = order.index(pos1) if pos1 in order else 0
            i2 = order.index(pos2) if pos2 in order else 0
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


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Poker GTO Analyzer (CLI)")
    parser.add_argument("--site", choices=["winamax", "coinpoker"], default="coinpoker")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--solver-path", type=str, default="./TexasSolver")
    parser.add_argument("--rendercolor-x", type=int, default=1920)
    parser.add_argument("--rendercolor-y", type=int, default=0)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    args = parser.parse_args()

    config = Config(site=args.site, debug_ocr=args.debug)
    config.capture.rendercolor_x = args.rendercolor_x
    config.capture.rendercolor_y = args.rendercolor_y
    config.capture.width = args.width
    config.capture.height = args.height
    config.solver.binary_path = args.solver_path
    config.window.overlay_x = args.rendercolor_x
    config.window.overlay_y = args.rendercolor_y
    config.window.overlay_width = args.width
    config.window.overlay_height = args.height

    analyzer = PokerAnalyzer(config)
    analyzer.run()


if __name__ == "__main__":
    main()
