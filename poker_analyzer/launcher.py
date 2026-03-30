"""Launcher GUI — config + control panel for the analyzer.

The window stays open after START as a control panel:
- Toggle debug OCR rectangles
- Toggle exploitative mode
- Stop/restart analysis
"""

import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog

import cv2
import numpy as np

# Dark theme
BG = "#1a1a2e"
FG = "#e0e0e0"
ACCENT = "#0f3460"
BUTTON_BG = "#16213e"
BUTTON_ACTIVE = "#1a4a7a"
HEADER_FG = "#00d2ff"
ENTRY_BG = "#2a2a4a"
GREEN = "#0a8a4a"
RED = "#8a2a2a"


class LauncherWindow:
    """Configuration + control panel."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Poker GTO Analyzer")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        w, h = 500, 650
        sx = (self.root.winfo_screenwidth() - w) // 2
        sy = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{sx}+{sy}")

        # State
        self._running = False
        self._analyzer = None
        self._thread = None

        self._build_ui()

    def _build_ui(self):
        # Title
        tk.Label(
            self.root, text="POKER GTO ANALYZER",
            font=("Consolas", 18, "bold"),
            fg=HEADER_FG, bg=BG, pady=10,
        ).pack(fill=tk.X)

        tk.Label(
            self.root, text="Stream Analysis Tool",
            font=("Consolas", 10), fg="#888", bg=BG,
        ).pack()

        # --- Config frame ---
        self.config_frame = tk.Frame(self.root, bg=BG, padx=30, pady=10)
        self.config_frame.pack(fill=tk.BOTH, expand=True)

        row = 0

        # Site
        self._label(self.config_frame, "Site :", row)
        self.site_var = tk.StringVar(value="coinpoker")
        ttk.Combobox(
            self.config_frame, textvariable=self.site_var,
            values=["coinpoker", "winamax"],
            state="readonly", width=20,
        ).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        # RenderColorQC path
        self._label(self.config_frame, "RenderColorQC :", row)
        rc_frame = tk.Frame(self.config_frame, bg=BG)
        rc_frame.grid(row=row, column=1, sticky="w", pady=4)
        self.rc_path_var = tk.StringVar(value="")
        tk.Entry(
            rc_frame, textvariable=self.rc_path_var,
            bg=ENTRY_BG, fg=FG, insertbackground=FG,
            width=16, font=("Consolas", 9),
        ).pack(side=tk.LEFT)
        tk.Button(
            rc_frame, text="...", command=self._browse_rendercolor,
            bg=BUTTON_BG, fg=FG, width=3,
        ).pack(side=tk.LEFT, padx=3)
        row += 1
        self._auto_detect_rendercolor()

        # RenderColor X
        self._label(self.config_frame, "Position X :", row)
        self.rcx_var = tk.StringVar(value="1920")
        tk.Entry(
            self.config_frame, textvariable=self.rcx_var,
            bg=ENTRY_BG, fg=FG, insertbackground=FG,
            width=22, font=("Consolas", 10),
        ).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        # RenderColor Y
        self._label(self.config_frame, "Position Y :", row)
        self.rcy_var = tk.StringVar(value="0")
        tk.Entry(
            self.config_frame, textvariable=self.rcy_var,
            bg=ENTRY_BG, fg=FG, insertbackground=FG,
            width=22, font=("Consolas", 10),
        ).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        # Resolution
        self._label(self.config_frame, "Resolution :", row)
        self.res_var = tk.StringVar(value="1920x1080")
        ttk.Combobox(
            self.config_frame, textvariable=self.res_var,
            values=["1920x1080", "2560x1440", "3840x2160"],
            state="readonly", width=20,
        ).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        # Solver path
        self._label(self.config_frame, "TexasSolver :", row)
        solver_frame = tk.Frame(self.config_frame, bg=BG)
        solver_frame.grid(row=row, column=1, sticky="w", pady=4)
        self.solver_var = tk.StringVar(value="./TexasSolver")
        tk.Entry(
            solver_frame, textvariable=self.solver_var,
            bg=ENTRY_BG, fg=FG, insertbackground=FG,
            width=16, font=("Consolas", 9),
        ).pack(side=tk.LEFT)
        tk.Button(
            solver_frame, text="...", command=self._browse_solver,
            bg=BUTTON_BG, fg=FG, width=3,
        ).pack(side=tk.LEFT, padx=3)
        row += 1

        # Auto-launch checkbox
        self.auto_launch_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            self.config_frame, text="Auto-launch RenderColorQC",
            variable=self.auto_launch_var,
            bg=BG, fg=FG, selectcolor=ENTRY_BG,
            activebackground=BG, activeforeground=FG,
            font=("Consolas", 9),
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=3)
        row += 1

        # --- Control panel (shown after START) ---
        self.control_frame = tk.Frame(self.root, bg=BG, padx=30, pady=5)

        # Debug toggle
        self.debug_var = tk.BooleanVar(value=False)
        self.debug_btn = tk.Button(
            self.control_frame,
            text="DEBUG OCR: OFF",
            command=self._toggle_debug,
            bg=BUTTON_BG, fg=FG, activebackground=BUTTON_ACTIVE,
            font=("Consolas", 11, "bold"),
            width=25, height=1,
        )
        self.debug_btn.pack(pady=5)

        # Exploit toggle
        self.exploit_var = tk.BooleanVar(value=True)
        self.exploit_btn = tk.Button(
            self.control_frame,
            text="MODE: EXP + GTO",
            command=self._toggle_exploit,
            bg=BUTTON_BG, fg=FG, activebackground=BUTTON_ACTIVE,
            font=("Consolas", 11, "bold"),
            width=25, height=1,
        )
        self.exploit_btn.pack(pady=5)

        # Status label
        self.status_var = tk.StringVar(value="")
        self.status_label = tk.Label(
            self.control_frame, textvariable=self.status_var,
            font=("Consolas", 9), fg="#888", bg=BG,
        )
        self.status_label.pack(pady=5)

        # Stop button
        self.stop_btn = tk.Button(
            self.control_frame,
            text="STOP",
            command=self._stop,
            bg=RED, fg="white", activebackground="#6a1a1a",
            font=("Consolas", 12, "bold"),
            width=25, height=1,
        )
        self.stop_btn.pack(pady=10)

        # --- START button ---
        self.btn_frame = tk.Frame(self.root, bg=BG, pady=10)
        self.btn_frame.pack(fill=tk.X)

        self.start_btn = tk.Button(
            self.btn_frame, text="START",
            command=self._start,
            bg=GREEN, fg="white", activebackground="#0c6a3a",
            font=("Consolas", 14, "bold"),
            width=20, height=2, cursor="hand2",
        )
        self.start_btn.pack()

    def _label(self, parent, text, row):
        tk.Label(
            parent, text=text,
            font=("Consolas", 10, "bold"),
            fg=FG, bg=BG, anchor="e",
        ).grid(row=row, column=0, sticky="e", padx=(0, 10), pady=4)

    def _auto_detect_rendercolor(self):
        candidates = [
            os.path.expandvars(r"%USERPROFILE%\Downloads\RenderColorQC_v1.0.14.exe"),
            os.path.expandvars(r"%USERPROFILE%\Downloads\RenderColorQC_v1.0.14 (2).exe"),
            r"\\Mac\Home\Downloads\RenderColorQC_v1.0.14.exe",
            r"\\Mac\Home\Downloads\RenderColorQC_v1.0.14 (2).exe",
        ]
        for path in candidates:
            try:
                if os.path.isfile(path):
                    self.rc_path_var.set(path)
                    return
            except OSError:
                continue

    def _browse_rendercolor(self):
        path = filedialog.askopenfilename(
            title="Select RenderColorQC",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self.rc_path_var.set(path)

    def _browse_solver(self):
        path = filedialog.askopenfilename(
            title="Select TexasSolver",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self.solver_var.set(path)

    def _launch_rendercolor(self):
        rc_path = self.rc_path_var.get()
        if not rc_path or not os.path.isfile(rc_path):
            return
        try:
            subprocess.Popen(
                [rc_path],
                cwd=os.path.dirname(rc_path),
                creationflags=0x00000008 if sys.platform == "win32" else 0,
            )
            self.status_var.set("RenderColorQC started — click Start Render")
        except Exception as e:
            self.status_var.set(f"Error: {e}")

    def _start(self):
        """Start the analyzer in a background thread."""
        if self._running:
            return

        # Get config values
        site = self.site_var.get()
        rcx = int(self.rcx_var.get())
        rcy = int(self.rcy_var.get())
        solver_path = self.solver_var.get()
        res = self.res_var.get()

        try:
            width, height = res.split("x")
            width, height = int(width), int(height)
        except ValueError:
            width, height = 1920, 1080

        # Launch RenderColorQC if requested
        if self.auto_launch_var.get():
            self._launch_rendercolor()

        # Build config
        from poker_analyzer.config import Config
        config = Config(site=site, debug_ocr=self.debug_var.get())
        config.capture.rendercolor_x = rcx
        config.capture.rendercolor_y = rcy
        config.capture.width = width
        config.capture.height = height
        config.solver.binary_path = solver_path
        config.window.overlay_x = rcx
        config.window.overlay_y = rcy
        config.window.overlay_width = width
        config.window.overlay_height = height

        # Switch to control mode
        self.config_frame.pack_forget()
        self.btn_frame.pack_forget()
        self.control_frame.pack(fill=tk.BOTH, expand=True)
        self.status_var.set(f"Running — {site} — {width}x{height}")
        self._running = True

        # Start analyzer in background thread
        from poker_analyzer.main import PokerAnalyzer
        self._analyzer = PokerAnalyzer(config, 1, 1)
        self._analyzer._show_exploit = self.exploit_var.get()

        self._thread = threading.Thread(target=self._run_analyzer, daemon=True)
        self._thread.start()

    def _run_analyzer(self):
        """Run the analyzer (called in background thread)."""
        try:
            self._analyzer.run()
        except Exception as e:
            print(f"[ERROR] Analyzer crashed: {e}")
        finally:
            self._running = False
            # Switch back to config mode on main thread
            self.root.after(0, self._show_config)

    def _show_config(self):
        """Switch back to config view."""
        self.control_frame.pack_forget()
        self.config_frame.pack(fill=tk.BOTH, expand=True)
        self.btn_frame.pack(fill=tk.X)
        self.status_var.set("Stopped")

    def _toggle_debug(self):
        """Toggle debug OCR rectangles."""
        self.debug_var.set(not self.debug_var.get())
        on = self.debug_var.get()
        self.debug_btn.config(text=f"DEBUG OCR: {'ON' if on else 'OFF'}")
        if self._analyzer:
            self._analyzer.config.debug_ocr = on

    def _toggle_exploit(self):
        """Toggle exploitative mode."""
        self.exploit_var.set(not self.exploit_var.get())
        on = self.exploit_var.get()
        self.exploit_btn.config(text=f"MODE: {'EXP + GTO' if on else 'GTO ONLY'}")
        if self._analyzer:
            self._analyzer._show_exploit = on

    def _stop(self):
        """Stop the analyzer."""
        if self._analyzer:
            self._analyzer._stop_flag = True
        self._running = False
        self.status_var.set("Stopping...")

    def _on_close(self):
        """Close everything."""
        if self._analyzer:
            self._analyzer._stop_flag = True
        self._running = False
        self.root.after(500, self.root.destroy)

    def run(self):
        self.root.mainloop()


def main():
    launcher = LauncherWindow()
    launcher.run()


if __name__ == "__main__":
    main()
