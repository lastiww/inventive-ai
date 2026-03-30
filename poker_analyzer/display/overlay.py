"""Transparent overlay — draws EXP./GEN. labels on top of RenderColorQC.

Creates a transparent, always-on-top, click-through Tkinter window
that floats over the RenderColorQC stream. Only the labels are visible.
"""

import tkinter as tk
from poker_analyzer.models.game_state import GameState, PlayerStats, SolverResult


# Colors
TRANSPARENT_COLOR = "#010101"  # used as transparent key
EXP_BG = "#8B2222"
EXP_HEADER = "#AA3333"
GEN_BG = "#226B22"
GEN_HEADER = "#33AA33"
TEXT_WHITE = "#FFFFFF"
TEXT_YELLOW = "#FFFF00"
STAT_GRAY = "#AAAAAA"
DEBUG_GREEN = "#00FF00"


class OverlayDisplay:
    """Transparent overlay window — only labels are visible."""

    def __init__(self, x: int = 1920, y: int = 0, width: int = 1920, height: int = 1080):
        self._x = x
        self._y = y
        self._width = width
        self._height = height
        self.root: tk.Tk | None = None
        self.canvas: tk.Canvas | None = None
        self._built = False
        self._debug_items = []
        self._label_items = []

    def build(self):
        """Create the transparent overlay window."""
        self.root = tk.Tk()
        self.root.title("GTO Overlay")

        # Fullscreen transparent overlay
        self.root.geometry(f"{self._width}x{self._height}+{self._x}+{self._y}")
        self.root.overrideredirect(True)          # no title bar / borders
        self.root.attributes("-topmost", True)     # always on top
        self.root.attributes("-transparentcolor", TRANSPARENT_COLOR)  # transparent
        self.root.configure(bg=TRANSPARENT_COLOR)

        # Make click-through on Windows
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            # Find our window
            self.root.update_idletasks()
            overlay_hwnd = self.root.winfo_id()
            # Set WS_EX_LAYERED | WS_EX_TRANSPARENT for click-through
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x80000
            WS_EX_TRANSPARENT = 0x20
            style = ctypes.windll.user32.GetWindowLongW(overlay_hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                overlay_hwnd, GWL_EXSTYLE,
                style | WS_EX_LAYERED | WS_EX_TRANSPARENT
            )
        except Exception:
            pass

        # Canvas for drawing
        self.canvas = tk.Canvas(
            self.root,
            width=self._width,
            height=self._height,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
        )
        self.canvas.pack()

        self._built = True

    def update_labels(
        self,
        anchors: list[tuple[float, float]],
        game_state: GameState | None,
        gto_result: SolverResult | None,
        exploit_result: SolverResult | None,
    ):
        """Update the player labels on the overlay."""
        if not self._built or self.canvas is None:
            return

        # Clear old labels
        for item in self._label_items:
            self.canvas.delete(item)
        self._label_items.clear()

        if not anchors:
            return

        for i, (ax, ay) in enumerate(anchors):
            cx = int(ax * self._width)
            cy = int(ay * self._height)

            # Skip folded players
            if game_state and i < len(game_state.players):
                if not game_state.players[i].is_active:
                    continue

            # Draw EXP. label (left)
            if exploit_result and exploit_result.actions:
                self._draw_label(cx - 120, cy, "EXP.", exploit_result, EXP_BG, EXP_HEADER)

            # Draw GEN. label (right)
            if gto_result and gto_result.actions:
                self._draw_label(cx + 5, cy, "GEN.", gto_result, GEN_BG, GEN_HEADER)

    def _draw_label(self, x: int, y: int, title: str, result: SolverResult, bg: str, header_bg: str):
        """Draw a mini-label box on the canvas."""
        label_w = 110
        header_h = 16

        # Sort actions
        sorted_actions = sorted(result.actions.items(), key=lambda a: a[1], reverse=True)
        actions = [(name, freq) for name, freq in sorted_actions if freq >= 0.005]
        if not actions:
            return

        label_h = header_h + len(actions) * 15 + 4

        # Background
        bg_item = self.canvas.create_rectangle(
            x, y, x + label_w, y + label_h,
            fill=bg, outline="", stipple="gray50",
        )
        self._label_items.append(bg_item)

        # Header
        hdr_item = self.canvas.create_rectangle(
            x, y, x + label_w, y + header_h,
            fill=header_bg, outline="",
        )
        self._label_items.append(hdr_item)

        hdr_text = self.canvas.create_text(
            x + 5, y + header_h // 2,
            text=title, fill=TEXT_WHITE, anchor="w",
            font=("Consolas", 8, "bold"),
        )
        self._label_items.append(hdr_text)

        # Actions
        text_y = y + header_h + 10
        for action_name, freq in actions:
            pct = f"{freq * 100:.0f}%"
            name = action_name.upper()[:6]
            color = TEXT_YELLOW if freq > 0.5 else TEXT_WHITE

            item = self.canvas.create_text(
                x + 5, text_y,
                text=f"{name} {pct}", fill=color, anchor="w",
                font=("Consolas", 8),
            )
            self._label_items.append(item)
            text_y += 15

    def update_debug_rois(self, rois: list[tuple[tuple[int, int, int, int], str]] | None):
        """Draw/clear debug OCR rectangles."""
        if not self._built or self.canvas is None:
            return

        # Clear old debug items
        for item in self._debug_items:
            self.canvas.delete(item)
        self._debug_items.clear()

        if not rois:
            return

        for (x, y, w, h), label in rois:
            rect = self.canvas.create_rectangle(
                x, y, x + w, y + h,
                outline=DEBUG_GREEN, width=2,
            )
            self._debug_items.append(rect)

            text = self.canvas.create_text(
                x + 2, y - 2,
                text=label, fill=DEBUG_GREEN, anchor="sw",
                font=("Consolas", 7),
            )
            self._debug_items.append(text)

    def process_events(self):
        """Process Tkinter events (call from main loop)."""
        if self.root:
            try:
                self.root.update_idletasks()
                self.root.update()
            except tk.TclError:
                pass

    def destroy(self):
        if self.root:
            self.root.destroy()
            self.root = None
