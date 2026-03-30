"""Video capture — screen region capture at RenderColorQC position.

Captures the screen region where RenderColorQC renders the stream
(NOT the RenderColorQC application window itself).
"""

import sys

import cv2
import numpy as np

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

from poker_analyzer.config import CaptureConfig, WindowConfig


class VideoCapture:
    """Captures screen region where RenderColorQC displays the stream.

    RenderColorQC renders the capture card stream at position X/Y on screen.
    We capture that screen region directly (not the app window).
    """

    def __init__(self, capture_config: CaptureConfig, window_config: WindowConfig):
        self.capture_config = capture_config
        self.window_config = window_config

    def open(self) -> bool:
        """Initialize capture."""
        print(f"[CAPTURE] Screen region: x={self.capture_config.rendercolor_x}, "
              f"y={self.capture_config.rendercolor_y}, "
              f"{self.capture_config.width}x{self.capture_config.height}")
        return True

    def read_frame(self) -> np.ndarray | None:
        """Capture the screen region where RenderColorQC renders."""
        if sys.platform == "win32":
            return self._capture_region_win32(
                self.capture_config.rendercolor_x,
                self.capture_config.rendercolor_y,
                self.capture_config.width,
                self.capture_config.height,
            )
        return None

    def _capture_region_win32(self, x: int, y: int, w: int, h: int) -> np.ndarray | None:
        """Capture a screen region using Windows GDI BitBlt."""
        try:
            from ctypes import windll

            hdc_screen = windll.user32.GetDC(0)
            hdc_mem = windll.gdi32.CreateCompatibleDC(hdc_screen)
            hbmp = windll.gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
            windll.gdi32.SelectObject(hdc_mem, hbmp)
            # SRCCOPY = 0x00CC0020
            windll.gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, x, y, 0x00CC0020)

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

            img = np.frombuffer(buffer, dtype=np.uint8).reshape(h, w, 4)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        except Exception as e:
            print(f"[CAPTURE ERROR] {e}")
            return None

    def release(self):
        """Cleanup."""
        print("[CAPTURE] Released.")
