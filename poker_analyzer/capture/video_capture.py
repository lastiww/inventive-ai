"""Video capture from RenderColorQC window via screen capture."""

import sys

import cv2
import numpy as np

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

from poker_analyzer.config import CaptureConfig, WindowConfig


class VideoCapture:
    """Captures video by screenshotting the RenderColorQC window.

    RenderColorQC handles the Orico IS6 capture card and displays the
    stream at a configurable x/y position. We capture that window's
    content instead of accessing the device directly (avoids conflicts).
    """

    def __init__(self, capture_config: CaptureConfig, window_config: WindowConfig):
        self.capture_config = capture_config
        self.window_config = window_config
        self._rendercolor_hwnd = None
        self._use_region_capture = False
        # Region to capture (x, y, w, h) — set from RenderColorQC position
        self._capture_region = (
            capture_config.rendercolor_x,
            capture_config.rendercolor_y,
            capture_config.width,
            capture_config.height,
        )

    def open(self) -> bool:
        """Find the RenderColorQC window or fall back to region capture."""
        if sys.platform == "win32":
            # Try to find RenderColorQC window by title
            self._rendercolor_hwnd = self._find_window("RenderColor")
            if self._rendercolor_hwnd:
                print(f"[CAPTURE] Found RenderColorQC window (hwnd={self._rendercolor_hwnd})")
            else:
                print("[CAPTURE] RenderColorQC window not found, using region capture")
                print(f"[CAPTURE] Region: ({self._capture_region[0]}, {self._capture_region[1]}) "
                      f"{self._capture_region[2]}x{self._capture_region[3]}")
                self._use_region_capture = True
        else:
            self._use_region_capture = True

        return True

    def read_frame(self) -> np.ndarray | None:
        """Capture a frame from the RenderColorQC window or screen region."""
        if sys.platform == "win32":
            if self._rendercolor_hwnd and not self._use_region_capture:
                return self._capture_window_win32(self._rendercolor_hwnd)
            else:
                return self._capture_region_win32(*self._capture_region)
        else:
            # Fallback for non-Windows
            return None

    def _find_window(self, title_substring: str) -> int | None:
        """Find a window by partial title match (Windows only)."""
        if sys.platform != "win32":
            return None

        result = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        def enum_callback(hwnd, lparam):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                if title_substring.lower() in buff.value.lower():
                    result.append(hwnd)
            return True

        ctypes.windll.user32.EnumWindows(enum_callback, 0)
        return result[0] if result else None

    def _capture_region_win32(self, x: int, y: int, w: int, h: int) -> np.ndarray | None:
        """Capture a screen region using Windows GDI."""
        try:
            import ctypes
            from ctypes import windll

            hdc_screen = windll.user32.GetDC(0)
            hdc_mem = windll.gdi32.CreateCompatibleDC(hdc_screen)
            hbmp = windll.gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
            windll.gdi32.SelectObject(hdc_mem, hbmp)
            windll.gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, x, y, 0x00CC0020)  # SRCCOPY

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
            windll.gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buffer, ctypes.byref(bmi), 0)

            # Cleanup
            windll.gdi32.DeleteObject(hbmp)
            windll.gdi32.DeleteDC(hdc_mem)
            windll.user32.ReleaseDC(0, hdc_screen)

            # Convert to numpy BGR
            img = np.frombuffer(buffer, dtype=np.uint8).reshape(h, w, 4)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        except Exception as e:
            print(f"[CAPTURE ERROR] {e}")
            return None

    def _capture_window_win32(self, hwnd: int) -> np.ndarray | None:
        """Capture a specific window's content (Windows only)."""
        try:
            from ctypes import windll

            # Get window dimensions
            rect = ctypes.wintypes.RECT()
            windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top

            if w <= 0 or h <= 0:
                return None

            hdc_win = windll.user32.GetDC(hwnd)
            hdc_mem = windll.gdi32.CreateCompatibleDC(hdc_win)
            hbmp = windll.gdi32.CreateCompatibleBitmap(hdc_win, w, h)
            windll.gdi32.SelectObject(hdc_mem, hbmp)
            windll.gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_win, 0, 0, 0x00CC0020)

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
            bmi.biHeight = -h
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0

            buffer = ctypes.create_string_buffer(w * h * 4)
            windll.gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buffer, ctypes.byref(bmi), 0)

            windll.gdi32.DeleteObject(hbmp)
            windll.gdi32.DeleteDC(hdc_mem)
            windll.user32.ReleaseDC(hwnd, hdc_win)

            img = np.frombuffer(buffer, dtype=np.uint8).reshape(h, w, 4)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        except Exception as e:
            print(f"[CAPTURE ERROR] {e}")
            return None

    def release(self):
        """Cleanup."""
        print("[CAPTURE] Released.")
