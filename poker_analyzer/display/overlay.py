"""GTO overlay — draws EXP./GEN. mini-labels next to each player.

Renders per-player GTO recommendations directly on the captured frame:
- EXP. (Exploitative) label on the left
- GEN. (GTO Pure) label on the right
Similar to the RTA overlay used by poker streamers.
"""

import cv2
import numpy as np

from poker_analyzer.models.game_state import GameState, PlayerStats, SolverResult, Street


# Colors (BGR for OpenCV)
EXP_BG = (140, 40, 40)         # dark red-ish for EXP. label
EXP_HEADER_BG = (180, 50, 50)  # slightly brighter header
GEN_BG = (40, 100, 40)         # dark green-ish for GEN. label
GEN_HEADER_BG = (50, 130, 50)  # slightly brighter header
TEXT_WHITE = (255, 255, 255)
TEXT_YELLOW = (0, 255, 255)
STAT_GRAY = (180, 180, 180)
SOLVING_AMBER = (0, 170, 255)
DEBUG_GREEN = (0, 255, 0)
DEBUG_BG = (0, 80, 0)

# Label dimensions
LABEL_W = 110   # width of each mini-label (COMP or GEN)
LABEL_H = 40    # height of each mini-label
HEADER_H = 14   # height of header bar ("EXP." / "GEN.")
GAP = 4         # gap between COMP and GEN labels
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SMALL = cv2.FONT_HERSHEY_PLAIN


class OverlayDisplay:
    """Draws per-player GTO labels directly on the captured video frame.

    For each player on the table, draws two small boxes:
    ┌─ EXP. ──┐  ┌── GEN. ──┐
    │ FOLD 100%│  │ FOLD 100%│
    │ CALL  0% │  │ CALL  0% │
    └──────────┘  └──────────┘
    """

    def __init__(self):
        self._status_text = "D=Debug | E=Exploit | Q=Quit"

    def set_status(self, text: str):
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
        player_label_anchors: list[tuple[float, float]] | None = None,
    ) -> np.ndarray:
        """Draw the overlay on the frame and return it."""
        display = frame.copy()
        fh, fw = display.shape[:2]

        # Draw debug OCR rectangles
        if debug_rois:
            self._draw_debug_rois(display, debug_rois)

        # Draw per-player labels
        if player_label_anchors and (gto_result or exploit_result):
            self._draw_player_labels(
                display, fw, fh,
                player_label_anchors,
                game_state,
                gto_result,
                exploit_result,
            )

        # Draw solving indicator
        if is_solving:
            cv2.putText(
                display, "SOLVING...",
                (fw - 180, 30),
                FONT, 0.6, SOLVING_AMBER, 2, cv2.LINE_AA,
            )

        # Status bar at bottom
        self._draw_status_bar(display, fw, fh)

        return display

    def _draw_player_labels(
        self,
        frame: np.ndarray,
        fw: int, fh: int,
        anchors: list[tuple[float, float]],
        state: GameState | None,
        gto_result: SolverResult | None,
        exploit_result: SolverResult | None,
    ):
        """Draw EXP./GEN. labels near each player."""
        for i, (ax, ay) in enumerate(anchors):
            # Convert normalized coords to pixels
            cx = int(ax * fw)
            cy = int(ay * fh)

            # Check if this player is active (skip folded players)
            if state and i < len(state.players):
                player = state.players[i]
                if not player.is_active:
                    continue

            # Total width = COMP label + gap + GEN label
            total_w = LABEL_W * 2 + GAP
            start_x = cx - total_w // 2
            start_y = cy - LABEL_H // 2

            # Draw EXP. label (left)
            if exploit_result:
                self._draw_mini_label(
                    frame, start_x, start_y,
                    "EXP.", exploit_result,
                    EXP_BG, EXP_HEADER_BG,
                )

            # Draw GEN. label (right)
            if gto_result:
                gen_x = start_x + LABEL_W + GAP
                self._draw_mini_label(
                    frame, gen_x, start_y,
                    "GEN.", gto_result,
                    GEN_BG, GEN_HEADER_BG,
                )

    def _draw_mini_label(
        self,
        frame: np.ndarray,
        x: int, y: int,
        title: str,
        result: SolverResult,
        bg_color: tuple,
        header_color: tuple,
    ):
        """Draw a single mini-label box with action frequencies."""
        fh, fw = frame.shape[:2]

        # Clamp to frame boundaries
        if x < 0:
            x = 0
        if y < 0:
            y = 0
        if x + LABEL_W > fw:
            x = fw - LABEL_W
        if y + LABEL_H > fh:
            y = fh - LABEL_H

        # Sort actions by frequency
        sorted_actions = sorted(
            result.actions.items(), key=lambda a: a[1], reverse=True
        )

        # Calculate dynamic height based on number of actions
        num_actions = sum(1 for _, f in sorted_actions if f >= 0.005)
        if num_actions == 0:
            num_actions = 1
        label_h = HEADER_H + num_actions * 13 + 4

        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (x, y), (x + LABEL_W, y + label_h), bg_color, -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

        # Header bar
        cv2.rectangle(frame, (x, y), (x + LABEL_W, y + HEADER_H), header_color, -1)
        cv2.putText(
            frame, title,
            (x + 3, y + HEADER_H - 3),
            FONT, 0.38, TEXT_WHITE, 1, cv2.LINE_AA,
        )

        # Action frequencies
        text_y = y + HEADER_H + 12
        for action_name, freq in sorted_actions:
            if freq < 0.005:
                continue

            pct = f"{freq * 100:.0f}%"
            name = action_name.upper()
            # Truncate long names
            if len(name) > 6:
                name = name[:6]

            line = f"{name} {pct}"
            color = TEXT_YELLOW if freq > 0.5 else TEXT_WHITE

            cv2.putText(
                frame, line,
                (x + 4, text_y),
                FONT, 0.35, color, 1, cv2.LINE_AA,
            )
            text_y += 13

    def _draw_debug_rois(
        self,
        frame: np.ndarray,
        rois: list[tuple[tuple[int, int, int, int], str]],
    ):
        """Draw OCR debug rectangles on the frame."""
        for (x, y, w, h), label in rois:
            cv2.rectangle(frame, (x, y), (x + w, y + h), DEBUG_GREEN, 2)
            label_size = cv2.getTextSize(label, FONT, 0.45, 1)[0]
            cv2.rectangle(
                frame,
                (x, y - label_size[1] - 6),
                (x + label_size[0] + 4, y),
                DEBUG_BG, -1,
            )
            cv2.putText(
                frame, label,
                (x + 2, y - 4),
                FONT, 0.45, DEBUG_GREEN, 1, cv2.LINE_AA,
            )

    def _draw_status_bar(self, frame: np.ndarray, fw: int, fh: int):
        """Draw status bar at the bottom."""
        bar_h = 22
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, fh - bar_h), (fw, fh), (20, 15, 10), -1)
        cv2.addWeighted(overlay, 0.70, frame, 0.30, 0, frame)
        cv2.putText(
            frame, self._status_text,
            (10, fh - 6),
            FONT, 0.40, STAT_GRAY, 1, cv2.LINE_AA,
        )
