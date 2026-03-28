"""Card detection using template matching."""

import os
from pathlib import Path

import cv2
import numpy as np

from poker_analyzer.models.game_state import Card, Rank, Suit


RANK_NAMES = {
    Rank.TWO: "2", Rank.THREE: "3", Rank.FOUR: "4", Rank.FIVE: "5",
    Rank.SIX: "6", Rank.SEVEN: "7", Rank.EIGHT: "8", Rank.NINE: "9",
    Rank.TEN: "T", Rank.JACK: "J", Rank.QUEEN: "Q", Rank.KING: "K",
    Rank.ACE: "A",
}

SUIT_NAMES = {
    Suit.HEARTS: "h", Suit.DIAMONDS: "d",
    Suit.CLUBS: "c", Suit.SPADES: "s",
}

TEMPLATES_DIR = Path(__file__).parent / "templates"


class CardDetector:
    """Detects cards using OpenCV template matching."""

    def __init__(self, site: str = "winamax", threshold: float = 0.8):
        self.site = site
        self.threshold = threshold
        self.rank_templates: dict[Rank, np.ndarray] = {}
        self.suit_templates: dict[Suit, np.ndarray] = {}
        self._load_templates()

    def _load_templates(self):
        """Load card rank and suit templates from disk."""
        template_dir = TEMPLATES_DIR / self.site

        if not template_dir.exists():
            print(f"[WARN] Template directory not found: {template_dir}")
            print(f"[WARN] Card detection will use color-based fallback.")
            return

        # Load rank templates (2.png, 3.png, ..., A.png)
        for rank in Rank:
            rank_file = template_dir / f"rank_{rank.value}.png"
            if rank_file.exists():
                tmpl = cv2.imread(str(rank_file), cv2.IMREAD_GRAYSCALE)
                if tmpl is not None:
                    self.rank_templates[rank] = tmpl

        # Load suit templates (h.png, d.png, c.png, s.png)
        for suit in Suit:
            suit_file = template_dir / f"suit_{suit.value}.png"
            if suit_file.exists():
                tmpl = cv2.imread(str(suit_file), cv2.IMREAD_GRAYSCALE)
                if tmpl is not None:
                    self.suit_templates[suit] = tmpl

        print(f"[OCR] Loaded {len(self.rank_templates)} rank + {len(self.suit_templates)} suit templates for {self.site}")

    def detect_card(self, card_roi: np.ndarray) -> Card | None:
        """Detect a card from a cropped ROI image.

        Args:
            card_roi: Cropped image of a single card.

        Returns:
            Detected Card or None if detection fails.
        """
        if card_roi is None or card_roi.size == 0:
            return None

        # Try template matching first
        if self.rank_templates and self.suit_templates:
            return self._detect_by_template(card_roi)

        # Fallback: color-based suit detection + OCR for rank
        return self._detect_by_color(card_roi)

    def _detect_by_template(self, card_roi: np.ndarray) -> Card | None:
        """Detect card using template matching."""
        gray = cv2.cvtColor(card_roi, cv2.COLOR_BGR2GRAY) if len(card_roi.shape) == 3 else card_roi

        # Detect rank (top portion of card)
        h, w = gray.shape[:2]
        rank_area = gray[0:h // 2, 0:w // 2]  # top-left quadrant has rank

        best_rank = None
        best_rank_score = 0.0

        for rank, tmpl in self.rank_templates.items():
            # Resize template to match ROI scale if needed
            tmpl_resized = self._resize_template(tmpl, rank_area)
            if tmpl_resized is None:
                continue

            result = cv2.matchTemplate(rank_area, tmpl_resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            if max_val > best_rank_score and max_val > self.threshold:
                best_rank_score = max_val
                best_rank = rank

        # Detect suit (below rank in top-left area)
        suit_area = gray[h // 4:h // 2, 0:w // 3]

        best_suit = None
        best_suit_score = 0.0

        for suit, tmpl in self.suit_templates.items():
            tmpl_resized = self._resize_template(tmpl, suit_area)
            if tmpl_resized is None:
                continue

            result = cv2.matchTemplate(suit_area, tmpl_resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            if max_val > best_suit_score and max_val > self.threshold:
                best_suit_score = max_val
                best_suit = suit

        if best_rank and best_suit:
            return Card(rank=best_rank, suit=best_suit)
        return None

    def _detect_by_color(self, card_roi: np.ndarray) -> Card | None:
        """Fallback: detect suit by color analysis.

        Red pixels → hearts/diamonds
        Black pixels → clubs/spades
        Shape analysis to distinguish within color group.
        """
        if len(card_roi.shape) < 3:
            return None

        hsv = cv2.cvtColor(card_roi, cv2.COLOR_BGR2HSV)

        # Red detection (hue wraps around 0/180)
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])

        red_mask = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)
        red_pixels = cv2.countNonZero(red_mask)

        total_pixels = card_roi.shape[0] * card_roi.shape[1]
        is_red = red_pixels > total_pixels * 0.05

        if is_red:
            # Could be hearts or diamonds — needs shape analysis
            # For now default to hearts (most common visual)
            suit = Suit.HEARTS
        else:
            suit = Suit.SPADES

        # Rank detection via OCR would go here
        # For now return None — template matching is preferred
        return None

    def _resize_template(self, tmpl: np.ndarray, target_area: np.ndarray) -> np.ndarray | None:
        """Resize template to fit within target area if needed."""
        th, tw = tmpl.shape[:2]
        ah, aw = target_area.shape[:2]

        if th > ah or tw > aw:
            scale = min(ah / th, aw / tw) * 0.9
            new_w = max(1, int(tw * scale))
            new_h = max(1, int(th * scale))
            return cv2.resize(tmpl, (new_w, new_h))

        return tmpl

    def detect_cards_in_region(
        self, frame: np.ndarray, regions: list[tuple[float, float, float, float]]
    ) -> list[Card | None]:
        """Detect cards from multiple ROI regions.

        Args:
            frame: Full table frame.
            regions: List of (x, y, w, h) as fractions of frame size.

        Returns:
            List of detected cards (None for undetected).
        """
        fh, fw = frame.shape[:2]
        cards = []

        for (rx, ry, rw, rh) in regions:
            x = int(rx * fw)
            y = int(ry * fh)
            w = int(rw * fw)
            h = int(rh * fh)

            roi = frame[y:y + h, x:x + w]
            card = self.detect_card(roi)
            cards.append(card)

        return cards
