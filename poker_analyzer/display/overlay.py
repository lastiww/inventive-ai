"""GTO overlay — draws directly on the captured frame using OpenCV.

Renders dual-panel GTO info + debug OCR rectangles on top of the
poker stream, all in a single fullscreen window on the right monitor.
"""

import cv2
import numpy as np

from poker_analyzer.models.game_state import GameState, PlayerStats, SolverResult, Street


# Color scheme (BGR for OpenCV)
BG_OVERLAY = (30, 26, 22)       # dark semi-transparent background
PANEL_BG = (62, 33, 22)         # panel background
TEXT_WHITE = (224, 224, 224)
HEADER_CYAN = (255, 210, 0)     # cyan in BGR
STAT_GRAY = (160, 160, 160)
SOLVING_AMBER = (0, 170, 255)
SEPARATOR = (80, 80, 80)

ACTION_COLORS = {
    "fold":  (170, 136, 136),
    "check": (204, 170, 136),
    "call":  (170, 204, 136),
    "bet":   (136, 170, 204),
    "raise": (136, 204, 204),
    "allin": (170, 136, 204),
}

# Bar dimensions
BAR_HEIGHT = 20
BAR_MAX_WIDTH = 160
PANEL_WIDTH = 340
PANEL_PADDING = 10


class OverlayDisplay:
    """Draws GTO overlay directly on the captured video frame.

    Layout on frame:
    ┌───────────────────────────────────────────────────────────┐
    │                    (poker stream)                         │
    │                                                           │
    │  ┌─── EXPLOITATIVE ──┐  ┌──── GTO PURE ────┐            │
    │  │ Stats: VPIP/PFR   │  │                    │            │
    │  │ ███ Bet 82%       │  │ ███ Bet 55%       │            │
    │  │ ██ Check 18%      │  │ ████ Check 45%    │            │
    │  │ EV: +1.2 BB       │  │ EV: +0.8 BB       │            │
    │  └───────────────────┘  └────────────────────┘            │
    │                                                           │
    │  [Debug OCR rectangles if enabled]                        │
    └───────────────────────────────────────────────────────────┘
    """

    def __init__(self):
        self._status_text = "Ready | D=Debug | E=Exploit | Q=Quit"

    def set_status(self, text: str):
        """Set status bar text."""
        self._status_text = text

    def draw_overlay(
        self,
        frame: np.ndarray,
        game_state: GameState | None = None,
        gto_result: SolverResult | None = None,
        exploit_result: SolverResult | None = None,
        opponent_stats: PlayerStats | None = None,
        is_solving: bool = False,
        debug_rois: list[tuple[tuple[int, int, int, int], str]] | None = None,
    ) -> np.ndarray:
        """Draw the full overlay on the frame and return it.

        Args:
            frame: The captured BGR frame.
            game_state: Current parsed game state.
            gto_result: GTO solver result.
            exploit_result: Exploitative solver result.
            opponent_stats: Opponent stats for exploitative panel.
            is_solving: Whether solver is currently running.
            debug_rois: OCR debug rectangles to draw.

        Returns:
            Frame with overlay drawn on top.
        """
        display = frame.copy()
        fh, fw = display.shape[:2]

        # Draw debug OCR rectangles (if enabled)
        if debug_rois:
            self._draw_debug_rois(display, debug_rois)

        # Draw game info bar at top
        self._draw_game_info(display, game_state, is_solving, fw)

        # Draw GTO panels at bottom-left area
        panel_y = fh - 280  # panels start 280px from bottom
        if panel_y < 100:
            panel_y = 100

        # Left panel — Exploitative
        panel_x1 = 10
        self._draw_panel(
            display, panel_x1, panel_y,
            "EXPLOITATIVE", exploit_result, opponent_stats,
        )

        # Right panel — GTO Pure
        panel_x2 = panel_x1 + PANEL_WIDTH + 15
        self._draw_panel(
            display, panel_x2, panel_y,
            "GTO PURE", gto_result, None,
        )

        # Status bar at bottom
        self._draw_status_bar(display, fw, fh)

        return display

    def _draw_debug_rois(
        self,
        frame: np.ndarray,
        rois: list[tuple[tuple[int, int, int, int], str]],
    ):
        """Draw OCR debug rectangles on the frame."""
        for (x, y, w, h), label in rois:
            # Green rectangle
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            # Label background
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
            cv2.rectangle(
                frame,
                (x, y - label_size[1] - 6),
                (x + label_size[0] + 4, y),
                (0, 80, 0), -1,
            )
            # Label text
            cv2.putText(
                frame, label,
                (x + 2, y - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA,
            )

    def _draw_game_info(
        self,
        frame: np.ndarray,
        state: GameState | None,
        is_solving: bool,
        fw: int,
    ):
        """Draw game state info bar at the top."""
        bar_h = 32

        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (fw, bar_h), (20, 15, 10), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        if state is None:
            text = "Waiting for game state..."
            cv2.putText(
                frame, text, (10, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, STAT_GRAY, 1, cv2.LINE_AA,
            )
            return

        parts = []
        parts.append(state.street.value.upper())

        if state.board:
            parts.append(f"Board: {state.board_str}")
        if state.pot_bb > 0:
            parts.append(f"Pot: {state.pot_bb:.1f}BB")

        hero = state.hero
        if hero and hero.hole_cards:
            c1, c2 = hero.hole_cards
            parts.append(f"Hero: {c1}{c2}")
            if hero.position:
                parts.append(f"({hero.position.value})")

        text = "  |  ".join(parts)
        color = SOLVING_AMBER if is_solving else HEADER_CYAN

        cv2.putText(
            frame, text, (10, 22),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA,
        )

        if is_solving:
            cv2.putText(
                frame, "SOLVING...", (fw - 140, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, SOLVING_AMBER, 1, cv2.LINE_AA,
            )

    def _draw_panel(
        self,
        frame: np.ndarray,
        px: int,
        py: int,
        title: str,
        result: SolverResult | None,
        stats: PlayerStats | None,
    ):
        """Draw a strategy panel (exploitative or GTO)."""
        panel_h = 260
        fh, fw = frame.shape[:2]

        # Clamp panel position
        if py + panel_h > fh:
            panel_h = fh - py - 5
        if panel_h < 80:
            return

        # Semi-transparent panel background
        overlay = frame.copy()
        cv2.rectangle(
            overlay,
            (px, py),
            (px + PANEL_WIDTH, py + panel_h),
            PANEL_BG, -1,
        )
        cv2.addWeighted(overlay, 0.80, frame, 0.20, 0, frame)

        # Panel border
        cv2.rectangle(
            frame,
            (px, py),
            (px + PANEL_WIDTH, py + panel_h),
            SEPARATOR, 1,
        )

        # Title
        cv2.putText(
            frame, title,
            (px + PANEL_PADDING, py + 22),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, HEADER_CYAN, 2, cv2.LINE_AA,
        )

        y_cursor = py + 40

        # Opponent stats (exploitative panel only)
        if stats:
            stats_lines = [
                f"VPIP: {stats.vpip:.0f}%  PFR: {stats.pfr:.0f}%  3B: {stats.three_bet:.0f}%",
                f"Fold CB: {stats.fold_to_cbet:.0f}%  AF: {stats.agg_factor:.1f}  H: {stats.hands_played}",
            ]
            for line in stats_lines:
                cv2.putText(
                    frame, line,
                    (px + PANEL_PADDING, y_cursor),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, STAT_GRAY, 1, cv2.LINE_AA,
                )
                y_cursor += 16
            y_cursor += 5

        # Separator line
        cv2.line(
            frame,
            (px + PANEL_PADDING, y_cursor),
            (px + PANEL_WIDTH - PANEL_PADDING, y_cursor),
            SEPARATOR, 1,
        )
        y_cursor += 8

        # Action frequencies
        if result is None or not result.actions:
            cv2.putText(
                frame, "No data",
                (px + PANEL_PADDING, y_cursor + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, STAT_GRAY, 1, cv2.LINE_AA,
            )
            return

        sorted_actions = sorted(
            result.actions.items(), key=lambda x: x[1], reverse=True
        )

        for action_name, freq in sorted_actions:
            if freq < 0.005:
                continue
            if y_cursor + BAR_HEIGHT + 5 > py + panel_h - 30:
                break

            # Get color
            action_key = action_name.split()[0].lower()
            color = ACTION_COLORS.get(action_key, TEXT_WHITE)

            # Action label
            label = f"{action_name.upper()}"
            cv2.putText(
                frame, label,
                (px + PANEL_PADDING, y_cursor + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA,
            )

            # Frequency bar
            bar_x = px + 110
            bar_w = int(BAR_MAX_WIDTH * freq)
            if bar_w < 2:
                bar_w = 2

            # Bar background
            cv2.rectangle(
                frame,
                (bar_x, y_cursor + 2),
                (bar_x + BAR_MAX_WIDTH, y_cursor + BAR_HEIGHT - 2),
                (40, 40, 60), -1,
            )
            # Bar fill
            cv2.rectangle(
                frame,
                (bar_x, y_cursor + 2),
                (bar_x + bar_w, y_cursor + BAR_HEIGHT - 2),
                color, -1,
            )

            # Percentage
            pct_text = f"{freq * 100:.0f}%"
            cv2.putText(
                frame, pct_text,
                (bar_x + BAR_MAX_WIDTH + 5, y_cursor + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, TEXT_WHITE, 1, cv2.LINE_AA,
            )

            y_cursor += BAR_HEIGHT + 4

        # EV at bottom of panel
        ev_y = py + panel_h - 10
        cv2.putText(
            frame, f"EV: {result.ev:+.2f} BB",
            (px + PANEL_PADDING, ev_y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, TEXT_WHITE, 1, cv2.LINE_AA,
        )

    def _draw_status_bar(self, frame: np.ndarray, fw: int, fh: int):
        """Draw status bar at the bottom."""
        bar_h = 24

        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, fh - bar_h), (fw, fh), (20, 15, 10), -1)
        cv2.addWeighted(overlay, 0.70, frame, 0.30, 0, frame)

        cv2.putText(
            frame, self._status_text,
            (10, fh - 7),
            cv2.FONT_HERSHEY_SIMPLEX, 0.42, STAT_GRAY, 1, cv2.LINE_AA,
        )
