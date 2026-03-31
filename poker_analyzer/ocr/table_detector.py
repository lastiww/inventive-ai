"""Auto-detect poker tables in a captured frame via green felt detection."""

import cv2
import numpy as np


def detect_tables(
    frame: np.ndarray,
    min_area_ratio: float = 0.03,
    max_tables: int = 6,
) -> list[tuple[int, int, int, int]]:
    """Detect poker table regions by finding the green felt.

    Returns tight bounding boxes around the felt + a small margin
    for player names/stacks immediately around the table.

    Args:
        frame: BGR image of the full screen capture.
        min_area_ratio: Minimum contour area as fraction of frame area.
        max_tables: Maximum number of tables to return.

    Returns:
        List of (x, y, w, h) bounding boxes in pixel coordinates.
    """
    fh, fw = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # CoinPoker / Winamax felt green range
    lower_green = np.array([30, 50, 50])
    upper_green = np.array([85, 255, 255])
    mask = cv2.inRange(hsv, lower_green, upper_green)

    # Morphology: close small gaps, then open to remove noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = fh * fw * min_area_ratio
    regions: list[tuple[int, int, int, int]] = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue

        x, y, w, h = cv2.boundingRect(cnt)

        # Aspect ratio filter — poker tables are wider than tall (roughly 2:1)
        ratio = w / max(h, 1)
        if ratio < 1.3 or ratio > 3.5:
            continue

        # Expand slightly: players sit just outside the felt edge
        # Keep it tight — 10% horizontal, 18% vertical (names above/below)
        pad_x = int(w * 0.10)
        pad_y = int(h * 0.18)

        x = max(0, x - pad_x)
        y = max(0, y - pad_y)
        w = min(fw - x, w + pad_x * 2)
        h = min(fh - y, h + pad_y * 2)

        regions.append((x, y, w, h))

    # Sort top-left to bottom-right
    regions.sort(key=lambda r: (r[1] // max(fh // 3, 1), r[0]))

    return regions[:max_tables]
