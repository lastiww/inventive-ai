"""GTO overlay display — dual panel: Exploitative (left) | GTO Pure (right)."""

import tkinter as tk
from tkinter import font as tkfont

from poker_analyzer.config import WindowConfig
from poker_analyzer.models.game_state import GameState, PlayerStats, SolverResult, Street


# Color scheme — dark theme, neutral colors (no red/green judgment)
BG_COLOR = "#1a1a2e"
PANEL_BG = "#16213e"
TEXT_COLOR = "#e0e0e0"
ACCENT_COLOR = "#0f3460"
HEADER_COLOR = "#00d2ff"
STAT_COLOR = "#a0a0a0"
ACTION_COLORS = {
    "fold": "#8888aa",
    "check": "#88aacc",
    "call": "#88ccaa",
    "bet": "#ccaa88",
    "raise": "#cccc88",
    "allin": "#cc88aa",
}
FREQ_BAR_BG = "#2a2a4a"
SOLVING_COLOR = "#ffaa00"


class OverlayDisplay:
    """Tkinter overlay window showing GTO and Exploitative strategies side by side.

    Layout:
    ┌──────────────────────────────────────────────┐
    │  [Game State: Board / Pot / Street / Hero]   │
    ├─────────────────────┬────────────────────────┤
    │   EXPLOITATIVE      │      GTO PURE          │
    │                     │                        │
    │  Opponent Stats:    │                        │
    │  VPIP: 35%          │                        │
    │  PFR: 12%           │                        │
    │  Fold to CB: 70%    │                        │
    │                     │                        │
    │  Strategy:          │  Strategy:             │
    │  ███████ Bet 82%    │  ███████ Bet 55%       │
    │  ███ Check 18%      │  █████ Check 45%       │
    │                     │                        │
    │  EV: +1.2 BB        │  EV: +0.8 BB           │
    └─────────────────────┴────────────────────────┘
    """

    def __init__(self, window_config: WindowConfig):
        self.window_config = window_config
        self.root: tk.Tk | None = None
        self._built = False

        # Widget references
        self._game_info_label: tk.Label | None = None
        self._exploit_frame: tk.Frame | None = None
        self._gto_frame: tk.Frame | None = None
        self._exploit_widgets: dict[str, tk.Widget] = {}
        self._gto_widgets: dict[str, tk.Widget] = {}
        self._status_label: tk.Label | None = None

    def build(self):
        """Build the Tkinter window."""
        self.root = tk.Tk()
        self.root.title("Poker GTO Analyzer")
        self.root.configure(bg=BG_COLOR)
        self.root.geometry(
            f"{self.window_config.overlay_width}x{self.window_config.overlay_height}"
            f"+{self.window_config.overlay_x}+{self.window_config.overlay_y}"
        )
        self.root.resizable(True, True)

        # Fonts
        self._title_font = tkfont.Font(family="Consolas", size=14, weight="bold")
        self._header_font = tkfont.Font(family="Consolas", size=11, weight="bold")
        self._body_font = tkfont.Font(family="Consolas", size=10)
        self._stat_font = tkfont.Font(family="Consolas", size=9)
        self._small_font = tkfont.Font(family="Consolas", size=8)

        # Top bar — game state info
        top_frame = tk.Frame(self.root, bg=ACCENT_COLOR, pady=5, padx=10)
        top_frame.pack(fill=tk.X)

        self._game_info_label = tk.Label(
            top_frame,
            text="Waiting for game state...",
            font=self._header_font,
            fg=HEADER_COLOR,
            bg=ACCENT_COLOR,
            anchor="w",
        )
        self._game_info_label.pack(fill=tk.X)

        # Main area — two panels side by side
        main_frame = tk.Frame(self.root, bg=BG_COLOR)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel — Exploitative
        self._exploit_frame = tk.Frame(main_frame, bg=PANEL_BG, bd=1, relief=tk.GROOVE)
        self._exploit_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        self._build_panel(self._exploit_frame, "EXPLOITATIVE", self._exploit_widgets)

        # Right panel — GTO Pure
        self._gto_frame = tk.Frame(main_frame, bg=PANEL_BG, bd=1, relief=tk.GROOVE)
        self._gto_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(2, 0))
        self._build_panel(self._gto_frame, "GTO PURE", self._gto_widgets)

        # Bottom status bar
        status_frame = tk.Frame(self.root, bg=ACCENT_COLOR, pady=3, padx=10)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self._status_label = tk.Label(
            status_frame,
            text="Ready | D=Debug OCR | Q=Quit",
            font=self._small_font,
            fg=STAT_COLOR,
            bg=ACCENT_COLOR,
            anchor="w",
        )
        self._status_label.pack(fill=tk.X)

        self._built = True

    def _build_panel(self, parent: tk.Frame, title: str, widgets: dict):
        """Build a strategy panel (exploitative or GTO)."""
        # Panel header
        header = tk.Label(
            parent, text=title,
            font=self._title_font, fg=HEADER_COLOR, bg=PANEL_BG,
            pady=5,
        )
        header.pack(fill=tk.X)
        widgets["header"] = header

        # Stats section (only meaningful for exploitative)
        stats_label = tk.Label(
            parent, text="",
            font=self._stat_font, fg=STAT_COLOR, bg=PANEL_BG,
            justify=tk.LEFT, anchor="w", padx=10,
        )
        stats_label.pack(fill=tk.X)
        widgets["stats"] = stats_label

        # Strategy section
        strategy_frame = tk.Frame(parent, bg=PANEL_BG, padx=10, pady=5)
        strategy_frame.pack(fill=tk.BOTH, expand=True)
        widgets["strategy_frame"] = strategy_frame

        # Action bars (created dynamically)
        widgets["action_labels"] = []
        widgets["action_bars"] = []

        # EV label
        ev_label = tk.Label(
            parent, text="",
            font=self._body_font, fg=TEXT_COLOR, bg=PANEL_BG,
            anchor="w", padx=10, pady=5,
        )
        ev_label.pack(fill=tk.X, side=tk.BOTTOM)
        widgets["ev"] = ev_label

    def update(
        self,
        game_state: GameState | None = None,
        gto_result: SolverResult | None = None,
        exploit_result: SolverResult | None = None,
        opponent_stats: PlayerStats | None = None,
        is_solving: bool = False,
    ):
        """Update the overlay with new data."""
        if not self._built or self.root is None:
            return

        # Update game info bar
        if game_state:
            self._update_game_info(game_state)

        # Update status
        if is_solving:
            self._status_label.config(text="Solving...", fg=SOLVING_COLOR)
        else:
            self._status_label.config(
                text="Ready | D=Debug OCR | Q=Quit", fg=STAT_COLOR
            )

        # Update exploitative panel
        self._update_strategy_panel(
            self._exploit_widgets,
            exploit_result,
            opponent_stats,
        )

        # Update GTO panel
        self._update_strategy_panel(
            self._gto_widgets,
            gto_result,
            opponent_stats=None,  # no stats shown on GTO panel
        )

    def _update_game_info(self, state: GameState):
        """Update the top game info bar."""
        parts = []

        # Street
        parts.append(state.street.value.upper())

        # Board
        if state.board:
            parts.append(f"Board: {state.board_str}")

        # Pot
        if state.pot_bb > 0:
            parts.append(f"Pot: {state.pot_bb:.1f}BB")

        # Hero cards
        hero = state.hero
        if hero and hero.hole_cards:
            c1, c2 = hero.hole_cards
            parts.append(f"Hero: {c1}{c2}")
            if hero.position:
                parts.append(f"({hero.position.value})")

        self._game_info_label.config(text="  |  ".join(parts))

    def _update_strategy_panel(
        self,
        widgets: dict,
        result: SolverResult | None,
        opponent_stats: PlayerStats | None = None,
    ):
        """Update a strategy panel with solver results."""
        # Update stats (exploitative panel only)
        if opponent_stats:
            stats_text = (
                f"VPIP: {opponent_stats.vpip:.0f}%  |  "
                f"PFR: {opponent_stats.pfr:.0f}%  |  "
                f"3Bet: {opponent_stats.three_bet:.0f}%\n"
                f"Fold to CB: {opponent_stats.fold_to_cbet:.0f}%  |  "
                f"AF: {opponent_stats.agg_factor:.1f}  |  "
                f"Hands: {opponent_stats.hands_played}"
            )
            widgets["stats"].config(text=stats_text)
        else:
            widgets["stats"].config(text="")

        # Clear old action bars
        strategy_frame = widgets["strategy_frame"]
        for widget in strategy_frame.winfo_children():
            widget.destroy()

        if result is None or not result.actions:
            no_data = tk.Label(
                strategy_frame,
                text="No data",
                font=self._body_font,
                fg=STAT_COLOR,
                bg=PANEL_BG,
            )
            no_data.pack(pady=20)
            widgets["ev"].config(text="")
            return

        # Sort actions by frequency (highest first)
        sorted_actions = sorted(
            result.actions.items(), key=lambda x: x[1], reverse=True
        )

        for action_name, freq in sorted_actions:
            if freq < 0.001:
                continue

            row = tk.Frame(strategy_frame, bg=PANEL_BG)
            row.pack(fill=tk.X, pady=2)

            # Action name
            color = ACTION_COLORS.get(action_name.split()[0].lower(), TEXT_COLOR)
            label = tk.Label(
                row,
                text=f"{action_name.upper()}",
                font=self._body_font,
                fg=color,
                bg=PANEL_BG,
                width=12,
                anchor="w",
            )
            label.pack(side=tk.LEFT)

            # Frequency bar
            bar_frame = tk.Frame(row, bg=FREQ_BAR_BG, height=18)
            bar_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
            bar_frame.pack_propagate(False)

            bar_width = max(1, freq)  # fraction 0-1
            bar = tk.Frame(bar_frame, bg=color)
            bar.place(relx=0, rely=0, relwidth=bar_width, relheight=1)

            # Percentage text
            pct_label = tk.Label(
                row,
                text=f"{freq * 100:.0f}%",
                font=self._body_font,
                fg=TEXT_COLOR,
                bg=PANEL_BG,
                width=5,
                anchor="e",
            )
            pct_label.pack(side=tk.RIGHT)

        # EV
        widgets["ev"].config(text=f"EV: {result.ev:+.2f} BB")

    def set_status(self, text: str):
        """Set status bar text."""
        if self._status_label:
            self._status_label.config(text=text)

    def process_events(self):
        """Process Tkinter events (call from main loop)."""
        if self.root:
            self.root.update_idletasks()
            self.root.update()

    def destroy(self):
        """Close the overlay window."""
        if self.root:
            self.root.destroy()
            self.root = None
