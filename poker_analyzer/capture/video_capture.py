"""Video capture — reads the RenderColorQC render window content.

Flow: Capture card → RenderColorQC → Our tool reads the render window → OCR → Overlay

Finds the RenderColorQC RENDER window (not the control panel) by looking
for the largest RenderColor window, and captures its content by HWND.
This avoids feedback loops since we read the window directly, not the screen.
"""

import sys

import cv2
import numpy as np

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

from poker_analyzer.config import CaptureConfig, WindowConfig


class VideoCapture:
    """Captures the RenderColorQC render window content by HWND.

    RenderColorQC creates two windows:
    1. Control panel (small): "RenderColorQC v1.0.14"
    2. Render window (large, 1920x1080): displays the capture card stream

    We find and capture the RENDER window (the large one).
    """

    def __init__(self, capture_config: CaptureConfig, window_config: WindowConfig):
        self.capture_config = capture_config
        self.window_config = window_config
        self._render_hwnd = None

    def open(self) -> bool:
        """Find the RenderColorQC render window."""
        if sys.platform != "win32":
            print("[CAPTURE] Windows required for RenderColorQC capture.")
            return False

        self._render_hwnd = self._find_render_window()
        if self._render_hwnd:
            print(f"[CAPTURE] Found RenderColorQC render window (hwnd={self._render_hwnd})")
            return True

        print("[CAPTURE] RenderColorQC render window not found yet.")
        print("[CAPTURE] Will retry each frame — make sure RenderColorQC is running with Start Render.")
        return True  # Don't fail, retry each frame

    def read_frame(self) -> np.ndarray | None:
        """Read a frame from the RenderColorQC render window."""
        if sys.platform != "win32":
            return None

        # Retry finding the render window if not found yet
        if self._render_hwnd is None or not self._is_window_valid(self._render_hwnd):
            self._render_hwnd = self._find_render_window()
            if self._render_hwnd is None:
                return None

        return self._capture_window(self._render_hwnd)

    def _find_render_window(self) -> int | None:
        """Find the RenderColorQC render window (the large one).

        Strategy: enumerate all windows containing "RenderColor" or belonging
        to the same process, and pick the largest one (the render window).
        """
        candidates = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        def enum_callback(hwnd, lparam):
            if not ctypes.windll.user32.IsWindowVisible(hwnd):
                return True

            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
            else:
                title = ""

            # Get window size
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top

            # Get window position
            point = ctypes.wintypes.POINT(0, 0)
            ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(point))

            # Look for RenderColor windows
            if "rendercolor" in title.lower() or "render" in title.lower():
                candidates.append({
                    "hwnd": hwnd,
                    "title": title,
                    "width": w,
                    "height": h,
                    "x": point.x,
                    "y": point.y,
                    "area": w * h,
                })

            # Also check for windows at the rendercolor position that are large
            # (the render window might not have a title)
            elif w >= 1280 and h >= 720:
                if abs(point.x - self.capture_config.rendercolor_x) < 100:
                    candidates.append({
                        "hwnd": hwnd,
                        "title": title or "(no title)",
                        "width": w,
                        "height": h,
                        "x": point.x,
                        "y": point.y,
                        "area": w * h,
                    })

            return True

        ctypes.windll.user32.EnumWindows(enum_callback, 0)

        if not candidates:
            return None

        # Print found candidates for debugging
        for c in candidates:
            print(f"  [WINDOW] '{c['title']}' {c['width']}x{c['height']} at ({c['x']},{c['y']})")

        # Prefer the largest window (render window is fullscreen 1920x1080)
        # If multiple, prefer the one at rendercolor_x position
        candidates.sort(key=lambda c: (
            abs(c["x"] - self.capture_config.rendercolor_x) < 100,  # at correct position
            c["area"],  # largest
        ), reverse=True)

        best = candidates[0]
        print(f"  [SELECTED] '{best['title']}' {best['width']}x{best['height']} at ({best['x']},{best['y']})")
        return best["hwnd"]

    def _is_window_valid(self, hwnd: int) -> bool:
        """Check if window handle is still valid."""
        return bool(ctypes.windll.user32.IsWindow(hwnd))

    def _capture_window(self, hwnd: int) -> np.ndarray | None:
        """Capture window content by HWND using PrintWindow for reliable capture."""
        try:
            # Get window dimensions
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top

            if w <= 0 or h <= 0:
                return None

            # Use PrintWindow for reliable capture (works even if window is behind others)
            hdc_win = ctypes.windll.user32.GetDC(hwnd)
            hdc_mem = ctypes.windll.gdi32.CreateCompatibleDC(hdc_win)
            hbmp = ctypes.windll.gdi32.CreateCompatibleBitmap(hdc_win, w, h)
            ctypes.windll.gdi32.SelectObject(hdc_mem, hbmp)

            # Try PrintWindow first (PW_CLIENTONLY = 1, PW_RENDERFULLCONTENT = 2)
            result = ctypes.windll.user32.PrintWindow(hwnd, hdc_mem, 3)
            if not result:
                # Fallback to BitBlt
                ctypes.windll.gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_win, 0, 0, 0x00CC0020)

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", ctypes.c_uint32),
                    ("biWidth", ctypes.c_int32),
                    ("biHeight", ctypes.c_int32),
                    ("biPlanes", ctypes.c_uint16),
                    ("biBitCount", ctypes.c_uint16),
                    ("biCompression", ctypes.c_uint32),
                    ("biSizeImage", ctypes.c_uint32),
                    ("biXPelsPerMeter", ctypes.c_int32),
                    ("biYPelsPerMeter", ctypes.c_int32),
                    ("biClrUsed", ctypes.c_uint32),
                    ("biClrImportant", ctypes.c_uint32),
                ]

            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = w
            bmi.biHeight = -h  # top-down
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0

            buffer = ctypes.create_string_buffer(w * h * 4)
            ctypes.windll.gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buffer, ctypes.byref(bmi), 0)

            # Cleanup
            ctypes.windll.gdi32.DeleteObject(hbmp)
            ctypes.windll.gdi32.DeleteDC(hdc_mem)
            ctypes.windll.user32.ReleaseDC(hwnd, hdc_win)

            img = np.frombuffer(buffer, dtype=np.uint8).reshape(h, w, 4)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        except Exception as e:
            print(f"[CAPTURE ERROR] {e}")
            return None

    def release(self):
        """Cleanup."""
        self._render_hwnd = None
        print("[CAPTURE] Released.")
