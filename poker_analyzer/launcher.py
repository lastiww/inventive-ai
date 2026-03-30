"""Launcher GUI — configuration window before starting the analyzer.

Provides a simple Tkinter interface to configure:
- Poker site (CoinPoker / Winamax)
- Table layout (1x1, 2x1, 2x2, 3x2, 2x3)
- RenderColorQC position
- Debug mode
- Solver path
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog

from poker_analyzer.config import Config
from poker_analyzer.main import PokerAnalyzer


# Dark theme colors
BG = "#1a1a2e"
FG = "#e0e0e0"
ACCENT = "#0f3460"
BUTTON_BG = "#16213e"
BUTTON_ACTIVE = "#1a4a7a"
HEADER_FG = "#00d2ff"
ENTRY_BG = "#2a2a4a"


class LauncherWindow:
    """Configuration launcher window."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Poker GTO Analyzer")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        # Center window
        w, h = 480, 520
        sx = (self.root.winfo_screenwidth() - w) // 2
        sy = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{sx}+{sy}")

        self._build_ui()

    def _build_ui(self):
        # Title
        title = tk.Label(
            self.root,
            text="POKER GTO ANALYZER",
            font=("Consolas", 18, "bold"),
            fg=HEADER_FG, bg=BG,
            pady=15,
        )
        title.pack(fill=tk.X)

        subtitle = tk.Label(
            self.root,
            text="Stream Analysis Tool",
            font=("Consolas", 10),
            fg="#888", bg=BG,
        )
        subtitle.pack()

        # Main frame
        main = tk.Frame(self.root, bg=BG, padx=30, pady=15)
        main.pack(fill=tk.BOTH, expand=True)

        row = 0

        # --- Site ---
        self._label(main, "Site :", row)
        self.site_var = tk.StringVar(value="coinpoker")
        site_combo = ttk.Combobox(
            main, textvariable=self.site_var,
            values=["coinpoker", "winamax"],
            state="readonly", width=20,
        )
        site_combo.grid(row=row, column=1, sticky="w", pady=5)
        row += 1

        # --- Tables ---
        self._label(main, "Tables :", row)
        self.tables_var = tk.StringVar(value="1x1")
        tables_combo = ttk.Combobox(
            main, textvariable=self.tables_var,
            values=["1x1", "2x1", "1x2", "2x2", "3x2", "2x3"],
            state="readonly", width=20,
        )
        tables_combo.grid(row=row, column=1, sticky="w", pady=5)
        row += 1

        # --- RenderColorQC X ---
        self._label(main, "RenderColor X :", row)
        self.rcx_var = tk.StringVar(value="1920")
        rcx_entry = tk.Entry(
            main, textvariable=self.rcx_var,
            bg=ENTRY_BG, fg=FG, insertbackground=FG,
            width=22, font=("Consolas", 10),
        )
        rcx_entry.grid(row=row, column=1, sticky="w", pady=5)
        row += 1

        # --- RenderColorQC Y ---
        self._label(main, "RenderColor Y :", row)
        self.rcy_var = tk.StringVar(value="0")
        rcy_entry = tk.Entry(
            main, textvariable=self.rcy_var,
            bg=ENTRY_BG, fg=FG, insertbackground=FG,
            width=22, font=("Consolas", 10),
        )
        rcy_entry.grid(row=row, column=1, sticky="w", pady=5)
        row += 1

        # --- Resolution ---
        self._label(main, "Resolution :", row)
        self.res_var = tk.StringVar(value="1920x1080")
        res_combo = ttk.Combobox(
            main, textvariable=self.res_var,
            values=["1920x1080", "2560x1440", "3840x2160"],
            state="readonly", width=20,
        )
        res_combo.grid(row=row, column=1, sticky="w", pady=5)
        row += 1

        # --- Solver path ---
        self._label(main, "TexasSolver :", row)
        solver_frame = tk.Frame(main, bg=BG)
        solver_frame.grid(row=row, column=1, sticky="w", pady=5)

        self.solver_var = tk.StringVar(value="./TexasSolver")
        solver_entry = tk.Entry(
            solver_frame, textvariable=self.solver_var,
            bg=ENTRY_BG, fg=FG, insertbackground=FG,
            width=16, font=("Consolas", 10),
        )
        solver_entry.pack(side=tk.LEFT)

        browse_btn = tk.Button(
            solver_frame, text="...",
            command=self._browse_solver,
            bg=BUTTON_BG, fg=FG, activebackground=BUTTON_ACTIVE,
            width=3,
        )
        browse_btn.pack(side=tk.LEFT, padx=5)
        row += 1

        # --- Debug ---
        self.debug_var = tk.BooleanVar(value=False)
        debug_check = tk.Checkbutton(
            main, text="Debug OCR (show detection rectangles)",
            variable=self.debug_var,
            bg=BG, fg=FG, selectcolor=ENTRY_BG,
            activebackground=BG, activeforeground=FG,
            font=("Consolas", 9),
        )
        debug_check.grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
        row += 1

        # --- Exploit mode ---
        self.exploit_var = tk.BooleanVar(value=True)
        exploit_check = tk.Checkbutton(
            main, text="Exploitative + GTO (EXP. labels)",
            variable=self.exploit_var,
            bg=BG, fg=FG, selectcolor=ENTRY_BG,
            activebackground=BG, activeforeground=FG,
            font=("Consolas", 9),
        )
        exploit_check.grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
        row += 1

        # --- Buttons ---
        btn_frame = tk.Frame(self.root, bg=BG, pady=15)
        btn_frame.pack(fill=tk.X)

        start_btn = tk.Button(
            btn_frame,
            text="START",
            command=self._start,
            bg="#0a8a4a",
            fg="white",
            activebackground="#0c6a3a",
            font=("Consolas", 14, "bold"),
            width=20, height=2,
            cursor="hand2",
        )
        start_btn.pack()

        # Keyboard hints
        hints = tk.Label(
            self.root,
            text="D = Debug OCR  |  E = Toggle Exploit  |  Q = Quit",
            font=("Consolas", 8),
            fg="#666", bg=BG,
            pady=5,
        )
        hints.pack(side=tk.BOTTOM)

    def _label(self, parent, text, row):
        lbl = tk.Label(
            parent, text=text,
            font=("Consolas", 10, "bold"),
            fg=FG, bg=BG, anchor="e",
        )
        lbl.grid(row=row, column=0, sticky="e", padx=(0, 10), pady=5)

    def _browse_solver(self):
        path = filedialog.askopenfilename(
            title="Select TexasSolver binary",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self.solver_var.set(path)

    def _start(self):
        """Build config and launch the analyzer."""
        # Parse values
        site = self.site_var.get()
        tables = self.tables_var.get()
        rcx = int(self.rcx_var.get())
        rcy = int(self.rcy_var.get())
        solver_path = self.solver_var.get()
        debug = self.debug_var.get()
        res = self.res_var.get()

        try:
            cols, rows = tables.split("x")
            cols, rows = int(cols), int(rows)
        except ValueError:
            cols, rows = 1, 1

        try:
            width, height = res.split("x")
            width, height = int(width), int(height)
        except ValueError:
            width, height = 1920, 1080

        # Build config
        config = Config(site=site, debug_ocr=debug)
        config.capture.rendercolor_x = rcx
        config.capture.rendercolor_y = rcy
        config.capture.width = width
        config.capture.height = height
        config.solver.binary_path = solver_path
        config.window.overlay_x = rcx
        config.window.overlay_y = rcy
        config.window.overlay_width = width
        config.window.overlay_height = height

        # Close launcher
        self.root.destroy()

        # Print config
        num_tables = cols * rows
        print("=" * 50)
        print("  POKER GTO ANALYZER")
        print("=" * 50)
        print(f"  Site:          {site}")
        print(f"  Tables:        {cols}x{rows} = {num_tables}")
        print(f"  RenderColorQC: ({rcx}, {rcy})")
        print(f"  Resolution:    {width}x{height}")
        print(f"  Solver:        {solver_path}")
        print(f"  Debug:         {debug}")
        print("=" * 50)

        # Launch analyzer
        analyzer = PokerAnalyzer(config, cols, rows)
        analyzer.run()

    def run(self):
        self.root.mainloop()


def main():
    launcher = LauncherWindow()
    launcher.run()


if __name__ == "__main__":
    main()
