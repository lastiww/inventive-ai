"""Data models for poker game state representation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Suit(Enum):
    HEARTS = "h"
    DIAMONDS = "d"
    CLUBS = "c"
    SPADES = "s"


class Rank(Enum):
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "T"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"


class Street(Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"


class Position(Enum):
    UTG = "UTG"
    UTG1 = "UTG+1"
    MP = "MP"
    CO = "CO"
    BTN = "BTN"
    SB = "SB"
    BB = "BB"


class ActionType(Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "allin"


@dataclass
class Card:
    rank: Rank
    suit: Suit

    def __str__(self) -> str:
        return f"{self.rank.value}{self.suit.value}"

    @classmethod
    def from_str(cls, s: str) -> "Card":
        """Parse card from string like 'Ah', 'Td', '2c'."""
        rank_str = s[0].upper()
        suit_str = s[1].lower()
        rank = Rank(rank_str)
        suit = Suit(suit_str)
        return cls(rank=rank, suit=suit)


@dataclass
class Action:
    action_type: ActionType
    amount: float = 0.0  # in BB

    def __str__(self) -> str:
        if self.action_type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
            return f"{self.action_type.value} {self.amount:.1f}BB"
        return self.action_type.value


@dataclass
class PlayerStats:
    """Tracked stats for exploitative play."""
    vpip: float = 0.0        # Voluntarily Put $ In Pot (%)
    pfr: float = 0.0         # Preflop Raise (%)
    three_bet: float = 0.0   # 3-Bet (%)
    fold_to_cbet: float = 0.0  # Fold to C-Bet (%)
    agg_factor: float = 0.0  # Aggression Factor
    hands_played: int = 0


@dataclass
class Player:
    name: str
    position: Optional[Position] = None
    stack_bb: float = 0.0
    hole_cards: Optional[tuple[Card, Card]] = None
    is_active: bool = True
    is_dealer: bool = False
    current_bet: float = 0.0  # current bet in BB
    stats: Optional[PlayerStats] = None


@dataclass
class HandRange:
    """Represents a range of hands with weights."""
    range_str: str  # e.g., "AA,KK,QQ,AKs,AKo"
    weights: dict[str, float] = field(default_factory=dict)  # hand -> weight (0-1)


@dataclass
class SolverResult:
    """Result from GTO solver."""
    actions: dict[str, float] = field(default_factory=dict)  # action -> frequency (0-1)
    ev: float = 0.0  # expected value in BB


@dataclass
class GameState:
    """Complete state of a poker hand."""
    # Table info
    site: str = "winamax"  # "winamax" or "coinpoker"
    table_name: str = ""
    max_players: int = 6

    # Players
    players: list[Player] = field(default_factory=list)

    # Hand state
    street: Street = Street.PREFLOP
    board: list[Card] = field(default_factory=list)
    pot_bb: float = 0.0
    hero_index: int = -1  # index of the player being analyzed

    # Action history
    actions: list[tuple[int, Action]] = field(default_factory=list)  # (player_index, action)

    # Solver results
    gto_result: Optional[SolverResult] = None
    exploitative_result: Optional[SolverResult] = None

    @property
    def hero(self) -> Optional[Player]:
        if 0 <= self.hero_index < len(self.players):
            return self.players[self.hero_index]
        return None

    @property
    def board_str(self) -> str:
        return "".join(str(c) for c in self.board)

    @property
    def active_players(self) -> list[Player]:
        return [p for p in self.players if p.is_active]

    def get_effective_stack(self) -> float:
        """Get effective stack (smallest stack among active players) in BB."""
        active = self.active_players
        if len(active) < 2:
            return 0.0
        stacks = sorted(p.stack_bb for p in active)
        return stacks[0]
