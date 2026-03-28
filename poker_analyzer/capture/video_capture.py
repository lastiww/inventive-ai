"""Video capture from HDMI capture card via OpenCV."""

import cv2
import numpy as np

from poker_analyzer.config import CaptureConfig, WindowConfig


class VideoCapture:
    """Captures video from an HDMI capture card and manages window display."""

    def __init__(self, capture_config: CaptureConfig, window_config: WindowConfig):
        self.capture_config = capture_config
        self.window_config = window_config
        self.cap: cv2.VideoCapture | None = None
        self._debug_mode = False
        self._debug_rois: list[tuple[tuple[int, int, int, int], str]] = []

    def open(self) -> bool:
        """Open the capture card device."""
        self.cap = cv2.VideoCapture(self.capture_config.device_id)
        if not self.cap.isOpened():
            print(f"[ERROR] Cannot open capture device {self.capture_config.device_id}")
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.capture_config.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.capture_config.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.capture_config.fps)

        # Create capture preview window
        cv2.namedWindow("Poker Stream", cv2.WINDOW_NORMAL)
        cv2.resizeWindow(
            "Poker Stream",
            self.window_config.capture_width,
            self.window_config.capture_height,
        )
        cv2.moveWindow(
            "Poker Stream",
            self.window_config.capture_x,
            self.window_config.capture_y,
        )

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        print(f"[CAPTURE] Opened device {self.capture_config.device_id}: {actual_w}x{actual_h} @ {actual_fps}fps")
        return True

    def read_frame(self) -> np.ndarray | None:
        """Read a single frame from the capture card."""
        if self.cap is None or not self.cap.isOpened():
            return None
        ret, frame = self.cap.read()
        if not ret:
            return None
        return frame

    def set_debug_rois(self, rois: list[tuple[tuple[int, int, int, int], str]]):
        """Set ROI rectangles to draw in debug mode.

        Args:
            rois: List of ((x, y, w, h), label) tuples in pixel coordinates.
        """
        self._debug_rois = rois

    def set_debug_mode(self, enabled: bool):
        """Toggle debug OCR rectangle display."""
        self._debug_mode = enabled
        print(f"[DEBUG] OCR rectangles {'ON' if enabled else 'OFF'}")

    def toggle_debug(self):
        """Toggle debug mode on/off."""
        self.set_debug_mode(not self._debug_mode)

    def show_frame(self, frame: np.ndarray):
        """Display the frame with optional debug rectangles."""
        display = frame.copy()

        if self._debug_mode and self._debug_rois:
            for (x, y, w, h), label in self._debug_rois:
                # Draw rectangle
                cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)
                # Draw label
                cv2.putText(
                    display, label,
                    (x, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1,
                )

        cv2.imshow("Poker Stream", display)

    def handle_key(self, key: int) -> str | None:
        """Handle keyboard input. Returns action string or None.

        Key bindings:
            'D' - Toggle debug OCR rectangles
            'Q' / ESC - Quit
        """
        if key == ord('d') or key == ord('D'):
            self.toggle_debug()
            return "toggle_debug"
        elif key == ord('q') or key == ord('Q') or key == 27:
            return "quit"
        return None

    def release(self):
        """Release the capture device and close windows."""
        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()
        print("[CAPTURE] Released.")
