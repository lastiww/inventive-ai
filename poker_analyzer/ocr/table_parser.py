"""Parse full table state from a video frame using OCR and template matching."""

import cv2
import numpy as np

from poker_analyzer.config import Config, SiteROI
from poker_analyzer.models.game_state import (
    Card, GameState, Player, PlayerStats, Position, Street,
)
from poker_analyzer.ocr.card_detector import CardDetector
from poker_analyzer.ocr.text_reader import TextReader


# Position mapping for 6-max by seat index relative to dealer
POSITIONS_6MAX = [Position.SB, Position.BB, Position.UTG, Position.MP, Position.CO, Position.BTN]
POSITIONS_HU = [Position.SB, Position.BB]


class TableParser:
    """Parses a poker table frame into a GameState object."""

    def __init__(self, config: Config):
        self.config = config
        self.roi = config.site_roi
        self.card_detector = CardDetector(site=config.site)
        self.text_reader = TextReader()
        self._last_state: GameState | None = None
        self._num_players_detected: int = 6

    def _auto_select_roi(self, frame: np.ndarray):
        """Auto-detect HU vs 6-max by checking if seats have visible stacks.

        Tries the 6-max ROI first. If only 2 seats have content,
        switches to HU ROI for better alignment.
        """
        full_roi = self.config.site_roi  # 6-max default
        fh, fw = frame.shape[:2]
        active_count = 0

        for region in full_roi.stack_regions:
            rx, ry, rw, rh = region
            x, y = int(rx * fw), int(ry * fh)
            w, h = int(rw * fw), int(rh * fh)
            roi_img = frame[max(0, y):y + h, max(0, x):x + w]
            if roi_img.size == 0:
                continue
            # A seat with a player has brighter pixels (text/avatar)
            gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
            if gray.mean() > 40:  # not just dark background
                active_count += 1

        if active_count <= 2:
            self.roi = self.config.get_roi_for_players(2)
            self._num_players_detected = 2
        else:
            self.roi = self.config.get_roi_for_players(active_count)
            self._num_players_detected = active_count

    def parse_frame(self, frame: np.ndarray) -> GameState:
        """Parse a single frame into a complete GameState.

        Args:
            frame: BGR image from capture card.

        Returns:
            Parsed GameState with all detected information.
        """
        # Auto-detect HU vs 6-max
        self._auto_select_roi(frame)

        state = GameState(site=self.config.site)

        # Detect board cards
        state.board = self._detect_board(frame)

        # Detect street from board card count
        state.street = self._detect_street(state.board)

        # Detect pot
        state.pot_bb = self._read_pot(frame)

        # Detect players (names, stacks, bets, positions)
        state.players = self._detect_players(frame)

        # Detect hero hole cards
        hero_cards = self._detect_hero_cards(frame)

        # Find hero (the player whose cards we can see)
        if hero_cards and len(hero_cards) == 2 and all(c is not None for c in hero_cards):
            # Hero is typically seat index 5 (bottom) on most sites
            if len(state.players) > 0:
                state.hero_index = len(state.players) - 1  # last seat = hero
                state.players[state.hero_index].hole_cards = (hero_cards[0], hero_cards[1])

        # Detect dealer button position and assign positions
        dealer_seat = self._detect_dealer(frame)
        if dealer_seat is not None:
            self._assign_positions(state.players, dealer_seat)

        # Read CoinPoker stats if available
        if self.config.site == "coinpoker":
            self._read_coinpoker_stats(frame, state.players)

        self._last_state = state
        return state

    def _detect_board(self, frame: np.ndarray) -> list[Card]:
        """Detect community cards on the board."""
        board_regions = [
            self.roi.board_card1,
            self.roi.board_card2,
            self.roi.board_card3,
            self.roi.board_card4,
            self.roi.board_card5,
        ]
        cards = self.card_detector.detect_cards_in_region(frame, board_regions)
        return [c for c in cards if c is not None]

    def _detect_hero_cards(self, frame: np.ndarray) -> list[Card | None]:
        """Detect hero's hole cards."""
        regions = [self.roi.hero_card1, self.roi.hero_card2]
        return self.card_detector.detect_cards_in_region(frame, regions)

    def _detect_street(self, board: list[Card]) -> Street:
        """Determine current street from board card count."""
        n = len(board)
        if n == 0:
            return Street.PREFLOP
        elif n == 3:
            return Street.FLOP
        elif n == 4:
            return Street.TURN
        elif n == 5:
            return Street.RIVER
        return Street.PREFLOP

    def _read_pot(self, frame: np.ndarray) -> float:
        """Read the pot total from the frame."""
        value, _ = self.text_reader.read_region_with_debug(frame, self.roi.pot_region)
        return value if value is not None else 0.0

    def _detect_players(self, frame: np.ndarray) -> list[Player]:
        """Detect all players at the table."""
        players = []
        num_seats = len(self.roi.stack_regions)

        for i in range(num_seats):
            player = Player(name=f"Seat{i + 1}")

            # Read player name
            if i < len(self.roi.name_regions):
                name = self._read_name(frame, self.roi.name_regions[i])
                if name:
                    player.name = name

            # Read stack size
            if i < len(self.roi.stack_regions):
                stack, _ = self.text_reader.read_region_with_debug(
                    frame, self.roi.stack_regions[i]
                )
                if stack is not None:
                    player.stack_bb = stack
                    player.is_active = True
                else:
                    player.is_active = False

            # Read current bet
            if i < len(self.roi.bet_regions):
                bet, _ = self.text_reader.read_region_with_debug(
                    frame, self.roi.bet_regions[i]
                )
                if bet is not None:
                    player.current_bet = bet

            players.append(player)

        return players

    def _read_name(self, frame: np.ndarray, region: tuple[float, float, float, float]) -> str | None:
        """Read a player name from a region."""
        fh, fw = frame.shape[:2]
        rx, ry, rw, rh = region
        x = int(rx * fw)
        y = int(ry * fh)
        w = int(rw * fw)
        h = int(rh * fh)

        roi = frame[y:y + h, x:x + w]
        return self.text_reader.read_player_name(roi)

    def _detect_dealer(self, frame: np.ndarray) -> int | None:
        """Detect which seat has the dealer button.

        Uses template matching or color detection for the 'D' button.
        """
        fh, fw = frame.shape[:2]

        for i, region in enumerate(self.roi.dealer_regions):
            rx, ry, rw, rh = region
            x = int(rx * fw)
            y = int(ry * fh)
            w = int(rw * fw)
            h = int(rh * fh)

            roi = frame[y:y + h, x:x + w]
            if self._is_dealer_button(roi):
                return i

        return None

    def _is_dealer_button(self, roi: np.ndarray) -> bool:
        """Check if a region contains the dealer button.

        The dealer button is typically a bright circular element.
        """
        if roi is None or roi.size == 0:
            return False

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Dealer button is usually bright white/yellow
        lower = np.array([15, 80, 200])
        upper = np.array([35, 255, 255])
        mask = cv2.inRange(hsv, lower, upper)

        white_ratio = cv2.countNonZero(mask) / max(1, roi.shape[0] * roi.shape[1])
        return white_ratio > 0.15

    def _assign_positions(self, players: list[Player], dealer_seat: int):
        """Assign positions based on dealer button location."""
        n = len(players)
        if n == 0:
            return

        positions = POSITIONS_HU if n <= 2 else POSITIONS_6MAX

        for i, player in enumerate(players):
            offset = (i - dealer_seat) % n
            if offset < len(positions):
                pos_index = (offset - 1) % len(positions)
                player.position = positions[pos_index]
                player.is_dealer = (i == dealer_seat)

    def _read_coinpoker_stats(self, frame: np.ndarray, players: list[Player]):
        """Read player stats displayed on CoinPoker tables."""
        if not self.roi.stats_regions:
            return

        fh, fw = frame.shape[:2]
        for i, region in enumerate(self.roi.stats_regions):
            if i >= len(players):
                break

            rx, ry, rw, rh = region
            x = int(rx * fw)
            y = int(ry * fh)
            w = int(rw * fw)
            h = int(rh * fh)

            roi = frame[y:y + h, x:x + w]
            stats_dict = self.text_reader.read_stats_text(roi)

            if stats_dict:
                players[i].stats = PlayerStats(
                    vpip=stats_dict.get("vpip", 0.0),
                    pfr=stats_dict.get("pfr", 0.0),
                    three_bet=stats_dict.get("three_bet", 0.0),
                    fold_to_cbet=stats_dict.get("fold_to_cbet", 0.0),
                )

    def get_debug_rois(self, frame: np.ndarray) -> list[tuple[tuple[int, int, int, int], str]]:
        """Get all ROI rectangles with labels for debug overlay.

        Returns:
            List of ((x, y, w, h), label) in pixel coordinates.
        """
        fh, fw = frame.shape[:2]
        rois = []

        def add_roi(region: tuple[float, float, float, float], label: str):
            rx, ry, rw, rh = region
            x = int(rx * fw)
            y = int(ry * fh)
            w = int(rw * fw)
            h = int(rh * fh)
            rois.append(((x, y, w, h), label))

        # Board cards
        for j, bc in enumerate([
            self.roi.board_card1, self.roi.board_card2, self.roi.board_card3,
            self.roi.board_card4, self.roi.board_card5,
        ]):
            board_label = f"Board {j + 1}"
            if self._last_state and j < len(self._last_state.board):
                board_label += f": {self._last_state.board[j]}"
            add_roi(bc, board_label)

        # Hero cards
        add_roi(self.roi.hero_card1, "Hero 1")
        add_roi(self.roi.hero_card2, "Hero 2")

        # Pot
        pot_label = "Pot"
        if self._last_state:
            pot_label += f": {self._last_state.pot_bb:.1f}BB"
        add_roi(self.roi.pot_region, pot_label)

        # Stacks
        for i, sr in enumerate(self.roi.stack_regions):
            stack_label = f"Stack {i + 1}"
            if self._last_state and i < len(self._last_state.players):
                p = self._last_state.players[i]
                stack_label = f"{p.name}: {p.stack_bb:.1f}BB"
            add_roi(sr, stack_label)

        # Bets
        for i, br in enumerate(self.roi.bet_regions):
            bet_label = f"Bet {i + 1}"
            if self._last_state and i < len(self._last_state.players):
                bet_val = self._last_state.players[i].current_bet
                if bet_val > 0:
                    bet_label += f": {bet_val:.1f}BB"
            add_roi(br, bet_label)

        # Dealer buttons
        for i, dr in enumerate(self.roi.dealer_regions):
            add_roi(dr, f"D{i + 1}")

        return rois
