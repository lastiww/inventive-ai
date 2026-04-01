"""Launcher GUI — config + control panel.

The window stays open after START as a control panel.
The transparent overlay is drawn on the right monitor on top of RenderColorQC.
OCR runs in a background thread.
"""

import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog

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

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Poker GTO Analyzer")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        w, h = 500, 780
        sx = (self.root.winfo_screenwidth() - w) // 2
        sy = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{sx}+{sy}")

        self._running = False
        self._analyzer = None
        self._ocr_thread = None

        self._build_config_ui()
        self._build_control_ui()

    # ─── Config UI ───

    def _build_config_ui(self):
        self.config_frame = tk.Frame(self.root, bg=BG, padx=30, pady=10)
        self.config_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            self.config_frame, text="POKER GTO ANALYZER",
            font=("Consolas", 18, "bold"), fg=HEADER_FG, bg=BG, pady=10,
        ).grid(row=0, column=0, columnspan=2)

        row = 1

        self._label(self.config_frame, "Site :", row)
        self.site_var = tk.StringVar(value="coinpoker")
        ttk.Combobox(
            self.config_frame, textvariable=self.site_var,
            values=["coinpoker", "winamax"], state="readonly", width=20,
        ).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        self._label(self.config_frame, "RenderColorQC :", row)
        rc_frame = tk.Frame(self.config_frame, bg=BG)
        rc_frame.grid(row=row, column=1, sticky="w", pady=4)
        self.rc_path_var = tk.StringVar(value="")
        tk.Entry(rc_frame, textvariable=self.rc_path_var, bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, width=16, font=("Consolas", 9)).pack(side=tk.LEFT)
        tk.Button(rc_frame, text="...", command=self._browse_rc,
                  bg=BUTTON_BG, fg=FG, width=3).pack(side=tk.LEFT, padx=3)
        row += 1
        self._auto_detect_rc()

        self._label(self.config_frame, "Position X :", row)
        self.rcx_var = tk.StringVar(value="1920")
        tk.Entry(self.config_frame, textvariable=self.rcx_var, bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, width=22, font=("Consolas", 10)).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        self._label(self.config_frame, "Position Y :", row)
        self.rcy_var = tk.StringVar(value="0")
        tk.Entry(self.config_frame, textvariable=self.rcy_var, bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, width=22, font=("Consolas", 10)).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        self._label(self.config_frame, "Resolution :", row)
        self.res_var = tk.StringVar(value="1920x1080")
        ttk.Combobox(
            self.config_frame, textvariable=self.res_var,
            values=["1920x1080", "2560x1440", "3840x2160"], state="readonly", width=20,
        ).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        self._label(self.config_frame, "Tables :", row)
        self.grid_var = tk.StringVar(value="1x1")
        ttk.Combobox(
            self.config_frame, textvariable=self.grid_var,
            values=["1x1", "1x2", "2x1", "2x2", "2x3", "3x2"], state="readonly", width=20,
        ).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        # --- Grid adjustment sliders ---
        sliders = [
            ("Gap X (px) :",      "gap_x_var",      0, 200, 0),
            ("Gap Y (px) :",      "gap_y_var",      0, 200, 0),
            ("Largeur (%%) :",    "width_pct_var",  30, 200, 100),
            ("Hauteur (%%) :",    "height_pct_var", 30, 200, 100),
            ("Décalage X :",      "shift_x_var",   -500, 500, 0),
            ("Décalage Y :",      "shift_y_var",   -500, 500, 0),
        ]
        for label_text, var_name, from_, to_, default in sliders:
            self._label(self.config_frame, label_text, row)
            var = tk.IntVar(value=default)
            setattr(self, var_name, var)
            tk.Scale(
                self.config_frame, from_=from_, to=to_, orient=tk.HORIZONTAL,
                variable=var, bg=BG, fg=FG, troughcolor=ENTRY_BG,
                highlightthickness=0, length=160, font=("Consolas", 8),
            ).grid(row=row, column=1, sticky="w", pady=1)
            row += 1

        self._label(self.config_frame, "TexasSolver :", row)
        sf = tk.Frame(self.config_frame, bg=BG)
        sf.grid(row=row, column=1, sticky="w", pady=4)
        self.solver_var = tk.StringVar(value="./TexasSolver")
        tk.Entry(sf, textvariable=self.solver_var, bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, width=16, font=("Consolas", 9)).pack(side=tk.LEFT)
        tk.Button(sf, text="...", command=self._browse_solver,
                  bg=BUTTON_BG, fg=FG, width=3).pack(side=tk.LEFT, padx=3)
        row += 1

        self.auto_launch_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            self.config_frame, text="Auto-launch RenderColorQC",
            variable=self.auto_launch_var, bg=BG, fg=FG, selectcolor=ENTRY_BG,
            activebackground=BG, activeforeground=FG, font=("Consolas", 9),
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=3)
        row += 1

        # START button
        tk.Button(
            self.config_frame, text="START", command=self._start,
            bg=GREEN, fg="white", activebackground="#0c6a3a",
            font=("Consolas", 14, "bold"), width=20, height=2, cursor="hand2",
        ).grid(row=row, column=0, columnspan=2, pady=15)

    # ─── Control UI ───

    def _build_control_ui(self):
        self.control_frame = tk.Frame(self.root, bg=BG, padx=30, pady=20)

        tk.Label(
            self.control_frame, text="POKER GTO ANALYZER",
            font=("Consolas", 16, "bold"), fg=HEADER_FG, bg=BG, pady=10,
        ).pack()

        self.status_var = tk.StringVar(value="")
        tk.Label(
            self.control_frame, textvariable=self.status_var,
            font=("Consolas", 10), fg="#888", bg=BG,
        ).pack(pady=5)

        self.debug_var = tk.BooleanVar(value=False)
        self.debug_btn = tk.Button(
            self.control_frame, text="DEBUG OCR: OFF",
            command=self._toggle_debug,
            bg=BUTTON_BG, fg=FG, activebackground=BUTTON_ACTIVE,
            font=("Consolas", 12, "bold"), width=25, height=2,
        )
        self.debug_btn.pack(pady=8)

        self.exploit_var = tk.BooleanVar(value=True)
        self.exploit_btn = tk.Button(
            self.control_frame, text="MODE: EXP + GTO",
            command=self._toggle_exploit,
            bg=BUTTON_BG, fg=FG, activebackground=BUTTON_ACTIVE,
            font=("Consolas", 12, "bold"), width=25, height=2,
        )
        self.exploit_btn.pack(pady=8)

        # ─── Live adjustment sliders ───
        tk.Label(
            self.control_frame, text="AJUSTEMENTS",
            font=("Consolas", 10, "bold"), fg="#888", bg=BG,
        ).pack(pady=(10, 2))

        adj_frame = tk.Frame(self.control_frame, bg=BG)
        adj_frame.pack(fill=tk.X)

        live_sliders = [
            ("Gap X",       self.gap_x_var,      0, 200),
            ("Gap Y",       self.gap_y_var,      0, 200),
            ("Largeur %",   self.width_pct_var,  30, 200),
            ("Hauteur %",   self.height_pct_var, 30, 200),
            ("Décalage X",  self.shift_x_var,   -500, 500),
            ("Décalage Y",  self.shift_y_var,   -500, 500),
        ]
        for i, (label, var, from_, to_) in enumerate(live_sliders):
            tk.Label(adj_frame, text=label, font=("Consolas", 8), fg=FG, bg=BG
                     ).grid(row=i, column=0, sticky="e", padx=4)
            tk.Scale(
                adj_frame, from_=from_, to=to_, orient=tk.HORIZONTAL,
                variable=var,
                bg=BG, fg=FG, troughcolor=ENTRY_BG, highlightthickness=0,
                length=140, font=("Consolas", 7),
            ).grid(row=i, column=1, pady=0)

        tk.Button(
            self.control_frame, text="STOP",
            command=self._stop,
            bg=RED, fg="white", activebackground="#6a1a1a",
            font=("Consolas", 12, "bold"), width=25, height=2,
        ).pack(pady=10)

    # ─── Helpers ───

    def _label(self, parent, text, row):
        tk.Label(parent, text=text, font=("Consolas", 10, "bold"),
                 fg=FG, bg=BG, anchor="e").grid(row=row, column=0, sticky="e", padx=(0, 10), pady=4)

    def _auto_detect_rc(self):
        for path in [
            os.path.expandvars(r"%USERPROFILE%\Downloads\RenderColorQC_v1.0.14.exe"),
            os.path.expandvars(r"%USERPROFILE%\Downloads\RenderColorQC_v1.0.14 (2).exe"),
            r"\\Mac\Home\Downloads\RenderColorQC_v1.0.14.exe",
            r"\\Mac\Home\Downloads\RenderColorQC_v1.0.14 (2).exe",
        ]:
            try:
                if os.path.isfile(path):
                    self.rc_path_var.set(path)
                    return
            except OSError:
                continue

    def _browse_rc(self):
        p = filedialog.askopenfilename(title="Select RenderColorQC", filetypes=[("Executable", "*.exe")])
        if p: self.rc_path_var.set(p)

    def _browse_solver(self):
        p = filedialog.askopenfilename(title="Select TexasSolver", filetypes=[("Executable", "*.exe")])
        if p: self.solver_var.set(p)

    def _launch_rendercolor(self):
        rc = self.rc_path_var.get()
        if not rc or not os.path.isfile(rc):
            return
        try:
            subprocess.Popen([rc], cwd=os.path.dirname(rc),
                             creationflags=0x00000008 if sys.platform == "win32" else 0)
        except Exception as e:
            print(f"[ERROR] {e}")

    # ─── Start / Stop ───

    def _start(self):
        if self._running:
            return

        site = self.site_var.get()
        rcx = int(self.rcx_var.get())
        rcy = int(self.rcy_var.get())
        res = self.res_var.get()
        try:
            width, height = res.split("x")
            width, height = int(width), int(height)
        except ValueError:
            width, height = 1920, 1080

        # Parse grid layout (e.g. "2x3" → cols=2, rows=3)
        grid_str = self.grid_var.get()
        try:
            cols, rows = grid_str.split("x")
            grid_cols, grid_rows = int(cols), int(rows)
        except ValueError:
            grid_cols, grid_rows = 1, 1

        if self.auto_launch_var.get():
            self._launch_rendercolor()

        from poker_analyzer.config import Config
        config = Config(site=site, debug_ocr=self.debug_var.get())
        config.grid_cols = grid_cols
        config.grid_rows = grid_rows
        config.grid_gap_x = self.gap_x_var.get()
        config.grid_gap_y = self.gap_y_var.get()
        config.grid_width_pct = self.width_pct_var.get()
        config.grid_height_pct = self.height_pct_var.get()
        config.grid_shift_x = self.shift_x_var.get()
        config.grid_shift_y = self.shift_y_var.get()
        config.capture.rendercolor_x = rcx
        config.capture.rendercolor_y = rcy
        config.capture.width = width
        config.capture.height = height
        config.solver.binary_path = self.solver_var.get()
        config.window.overlay_x = rcx
        config.window.overlay_y = rcy
        config.window.overlay_width = width
        config.window.overlay_height = height

        # Switch to control panel
        self.config_frame.pack_forget()
        self.control_frame.pack(fill=tk.BOTH, expand=True)
        n_tables = grid_cols * grid_rows
        self.status_var.set(f"Running — {site} — {width}x{height} — {n_tables} table(s)")
        self._running = True

        # Create analyzer
        from poker_analyzer.main import PokerAnalyzer
        self._analyzer = PokerAnalyzer(config)
        self._analyzer._show_exploit = self.exploit_var.get()

        # Initialize capture
        self._analyzer.capture.open()

        # Create the transparent overlay (on main Tk thread via Toplevel)
        from poker_analyzer.display.overlay import OverlayDisplay
        self._analyzer._overlay = OverlayDisplay(
            x=config.window.overlay_x,
            y=config.window.overlay_y,
            width=config.window.overlay_width,
            height=config.window.overlay_height,
        )
        # Use Toplevel instead of new Tk
        self._analyzer._overlay.root = tk.Toplevel(self.root)
        overlay_root = self._analyzer._overlay.root
        overlay_root.title("GTO Overlay")
        overlay_root.geometry(f"{width}x{height}+{rcx}+{rcy}")
        overlay_root.overrideredirect(True)
        overlay_root.attributes("-topmost", True)
        overlay_root.attributes("-transparentcolor", "#010101")
        overlay_root.configure(bg="#010101")

        # Click-through
        try:
            import ctypes
            overlay_root.update_idletasks()
            hwnd = int(overlay_root.frame(), 16)
            GWL_EXSTYLE = -20
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, style | 0x80000 | 0x20  # WS_EX_LAYERED | WS_EX_TRANSPARENT
            )
        except Exception:
            pass

        canvas = tk.Canvas(overlay_root, width=width, height=height,
                           bg="#010101", highlightthickness=0)
        canvas.pack()
        self._analyzer._overlay.canvas = canvas
        self._analyzer._overlay._built = True
        self._analyzer._overlay._width = width
        self._analyzer._overlay._height = height

        # Start OCR loop with periodic Tk callback
        self._ocr_step()

    def _ocr_step(self):
        """One OCR step — called periodically by Tk mainloop."""
        if not self._running or not self._analyzer:
            return

        try:
            self._analyzer_step()
        except Exception as e:
            print(f"[ERROR] {e}")

        # Schedule next step (2000ms = 0.5 FPS — rectangles stay fixed between updates)
        self.root.after(2000, self._ocr_step)

    def _analyzer_step(self):
        """Single analysis step: capture → OCR → solve → update overlay."""
        analyzer = self._analyzer
        if not analyzer:
            return

        # Sync slider values (once per frame, not per pixel)
        self._sync_grid_params()

        frame = analyzer.capture.read_frame()
        if frame is None:
            return

        detected = analyzer.multi.update_tables(frame)

        for i, (table_frame, table) in enumerate(detected):
            table.game_state = table.parser.parse_frame(table_frame)

            now = time.time()
            if analyzer._detect_state_change(table) and (now - table.last_solve_time) > 2.0:
                analyzer._trigger_solve(table)
                table.last_solve_time = now

            table.gto_result = table.solver.get_result()
            if analyzer._show_exploit and table.gto_result and table.game_state:
                opponent = analyzer._find_opponent(table.game_state)
                if opponent:
                    table.exploit_result = table.game_state.exploitative_result

            # Update overlay labels
            if analyzer._overlay:
                anchors = analyzer.multi.get_label_anchors(i)
                analyzer._overlay.update_labels(
                    anchors, table.game_state,
                    table.gto_result,
                    table.exploit_result if analyzer._show_exploit else None,
                )

        # Debug rects
        if analyzer._overlay:
            if analyzer.config.debug_ocr:
                rois = analyzer.multi.get_all_debug_rois(frame)
                analyzer._overlay.update_debug_rois(rois)
            else:
                analyzer._overlay.update_debug_rois(None)

    def _sync_grid_params(self):
        """Push slider values to multi-table manager (called once per OCR step)."""
        if self._analyzer and self._analyzer.multi:
            m = self._analyzer.multi
            m.gap_x = self.gap_x_var.get()
            m.gap_y = self.gap_y_var.get()
            m.width_pct = self.width_pct_var.get()
            m.height_pct = self.height_pct_var.get()
            m.shift_x = self.shift_x_var.get()
            m.shift_y = self.shift_y_var.get()

    def _toggle_debug(self):
        self.debug_var.set(not self.debug_var.get())
        on = self.debug_var.get()
        self.debug_btn.config(text=f"DEBUG OCR: {'ON' if on else 'OFF'}")
        if self._analyzer:
            self._analyzer.config.debug_ocr = on

    def _toggle_exploit(self):
        self.exploit_var.set(not self.exploit_var.get())
        on = self.exploit_var.get()
        self.exploit_btn.config(text=f"MODE: {'EXP + GTO' if on else 'GTO ONLY'}")
        if self._analyzer:
            self._analyzer._show_exploit = on

    def _stop(self):
        self._running = False
        if self._analyzer and self._analyzer._overlay:
            self._analyzer._overlay.destroy()
            self._analyzer._overlay = None
        if self._analyzer:
            self._analyzer.capture.release()
            self._analyzer = None
        self.control_frame.pack_forget()
        self.config_frame.pack(fill=tk.BOTH, expand=True)
        self.status_var.set("Stopped")

    def _on_close(self):
        self._stop()
        self.root.after(300, self.root.destroy)

    def run(self):
        self.root.mainloop()


def main():
    launcher = LauncherWindow()
    launcher.run()


if __name__ == "__main__":
    main()
