"""OCR text reader for pot, stacks, and bet amounts."""

import re

import cv2
import numpy as np
import pytesseract


class TextReader:
    """Reads numeric values (pot, stacks, bets) from poker table using Tesseract OCR."""

    def __init__(self):
        # Tesseract config optimized for numeric text
        self.config = "--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789.,BBKM "

    def read_bb_value(self, roi: np.ndarray) -> float | None:
        """Read a BB (big blind) value from a cropped region.

        Handles formats like:
            '275,2 BB', '99,5 BB', '183,4 BB'
            '275.2 BB', '99.5 BB'
            '1.5K BB' (thousands)
        """
        text = self._ocr_region(roi)
        if not text:
            return None
        return self._parse_bb_value(text)

    def read_pot_value(self, roi: np.ndarray) -> float | None:
        """Read pot value. Format: 'Pot total : 1,5 BB' or 'Pot total : 4 BB'."""
        text = self._ocr_region(roi)
        if not text:
            return None
        return self._parse_bb_value(text)

    def read_bet_value(self, roi: np.ndarray) -> float | None:
        """Read a bet amount from the table."""
        text = self._ocr_region(roi)
        if not text:
            return None
        return self._parse_bb_value(text)

    def read_player_name(self, roi: np.ndarray) -> str | None:
        """Read a player name from the table."""
        config = "--oem 3 --psm 7"
        text = self._ocr_region(roi, config=config)
        if not text or len(text.strip()) < 2:
            return None
        return text.strip()

    def read_stats_text(self, roi: np.ndarray) -> dict[str, float] | None:
        """Read player stats from CoinPoker table overlay.

        CoinPoker shows stats like: 'VPIP: 25 / PFR: 18 / 3B: 8'
        """
        config = "--oem 3 --psm 6"
        text = self._ocr_region(roi, config=config)
        if not text:
            return None
        return self._parse_stats(text)

    def _ocr_region(self, roi: np.ndarray, config: str | None = None) -> str | None:
        """Run OCR on a preprocessed ROI region."""
        if roi is None or roi.size == 0:
            return None

        processed = self._preprocess(roi)

        try:
            text = pytesseract.image_to_string(processed, config=config or self.config)
            return text.strip() if text else None
        except Exception as e:
            print(f"[OCR ERROR] {e}")
            return None

    def _preprocess(self, roi: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR accuracy.

        Steps:
        1. Convert to grayscale
        2. Upscale (small text needs higher resolution)
        3. Threshold to binary (white text on dark background)
        """
        # Convert to grayscale
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = roi.copy()

        # Upscale 3x for better OCR on small text
        h, w = gray.shape
        scaled = cv2.resize(gray, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)

        # Apply threshold — poker tables have white/bright text on dark background
        _, binary = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Check if text is dark on light or light on dark
        white_pixels = cv2.countNonZero(binary)
        total_pixels = binary.shape[0] * binary.shape[1]
        if white_pixels > total_pixels * 0.5:
            # Invert — we want white text on black
            binary = cv2.bitwise_not(binary)

        return binary

    def _parse_bb_value(self, text: str) -> float | None:
        """Parse a BB value from OCR text.

        Handles:
            '275,2 BB' → 275.2
            '99.5' → 99.5
            '1,5' → 1.5
            '4 BB' → 4.0
            '183,4BB' → 183.4
        """
        # Clean up text
        text = text.upper().strip()
        text = text.replace("BB", "").strip()
        text = text.replace(" ", "")

        # Handle comma as decimal separator (European format)
        text = text.replace(",", ".")

        # Handle K (thousands) and M (millions)
        multiplier = 1.0
        if text.endswith("K"):
            multiplier = 1000.0
            text = text[:-1]
        elif text.endswith("M"):
            multiplier = 1000000.0
            text = text[:-1]

        # Extract the numeric value
        match = re.search(r"(\d+\.?\d*)", text)
        if match:
            try:
                return float(match.group(1)) * multiplier
            except ValueError:
                return None
        return None

    def _parse_stats(self, text: str) -> dict[str, float] | None:
        """Parse player stats from CoinPoker stats text.

        Expected format: lines of 'STAT: VALUE' or 'STAT VALUE%'
        """
        stats = {}
        text = text.upper()

        # Match patterns like 'VPIP: 25', 'PFR 18', '3B: 8'
        patterns = {
            "vpip": r"VPIP[:\s]*(\d+\.?\d*)",
            "pfr": r"PFR[:\s]*(\d+\.?\d*)",
            "three_bet": r"3B(?:ET)?[:\s]*(\d+\.?\d*)",
            "fold_to_cbet": r"F(?:OLD)?.*CB(?:ET)?[:\s]*(\d+\.?\d*)",
        }

        for stat_name, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                try:
                    stats[stat_name] = float(match.group(1))
                except ValueError:
                    pass

        return stats if stats else None

    def read_region_with_debug(
        self, frame: np.ndarray, region: tuple[float, float, float, float]
    ) -> tuple[float | None, tuple[int, int, int, int]]:
        """Read a BB value from a region and return pixel coordinates for debug.

        Returns:
            (value, (x_px, y_px, w_px, h_px)) for debug overlay.
        """
        fh, fw = frame.shape[:2]
        rx, ry, rw, rh = region
        x = int(rx * fw)
        y = int(ry * fh)
        w = int(rw * fw)
        h = int(rh * fh)

        roi = frame[y:y + h, x:x + w]
        value = self.read_bb_value(roi)

        return value, (x, y, w, h)
