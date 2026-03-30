"""Video capture — reads screen region at RenderColorQC position for OCR only.

We don't display the captured frame. We just read the screen region
where RenderColorQC renders the stream, for OCR analysis.
The overlay is drawn as a separate transparent window on top.
"""

import sys

import cv2
import numpy as np

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

from poker_analyzer.config import CaptureConfig, WindowConfig


class VideoCapture:
    """Reads the screen region where RenderColorQC renders for OCR analysis.

    Does NOT display anything — just provides frames for OCR.
    """

    def __init__(self, capture_config: CaptureConfig, window_config: WindowConfig):
        self.capture_config = capture_config
        self.window_config = window_config

    def open(self) -> bool:
        x = self.capture_config.rendercolor_x
        y = self.capture_config.rendercolor_y
        w = self.capture_config.width
        h = self.capture_config.height
        print(f"[OCR] Reading screen region: ({x},{y}) {w}x{h}")
        return True

    def read_frame(self) -> np.ndarray | None:
        """Read the screen region for OCR analysis."""
        if sys.platform != "win32":
            return None
        return self._capture_region(
            self.capture_config.rendercolor_x,
            self.capture_config.rendercolor_y,
            self.capture_config.width,
            self.capture_config.height,
        )

    def _capture_region(self, x: int, y: int, w: int, h: int) -> np.ndarray | None:
        try:
            hdc_screen = ctypes.windll.user32.GetDC(0)
            hdc_mem = ctypes.windll.gdi32.CreateCompatibleDC(hdc_screen)
            hbmp = ctypes.windll.gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
            ctypes.windll.gdi32.SelectObject(hdc_mem, hbmp)
            ctypes.windll.gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, x, y, 0x00CC0020)

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
            ctypes.windll.gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buffer, ctypes.byref(bmi), 0)

            ctypes.windll.gdi32.DeleteObject(hbmp)
            ctypes.windll.gdi32.DeleteDC(hdc_mem)
            ctypes.windll.user32.ReleaseDC(0, hdc_screen)

            img = np.frombuffer(buffer, dtype=np.uint8).reshape(h, w, 4)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception as e:
            print(f"[CAPTURE ERROR] {e}")
            return None

    def release(self):
        print("[OCR] Released.")
