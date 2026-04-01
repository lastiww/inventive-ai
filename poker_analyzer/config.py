"""Configuration for the Poker Stream GTO Analyzer."""

from dataclasses import dataclass, field


@dataclass
class CaptureConfig:
    """Video capture settings."""
    device_id: int = 0  # capture card device index (fallback)
    width: int = 1920
    height: int = 1080
    fps: int = 30
    # RenderColorQC window position (where the stream is displayed)
    rendercolor_x: int = 1920  # x=1920 = second monitor
    rendercolor_y: int = 0


@dataclass
class WindowConfig:
    """Window positioning and scaling."""
    # Capture preview window
    capture_x: int = 0
    capture_y: int = 0
    capture_width: int = 960
    capture_height: int = 540

    # Overlay window (second monitor)
    overlay_x: int = 1920  # starts on second screen
    overlay_y: int = 0
    overlay_width: int = 960
    overlay_height: int = 540


@dataclass
class SiteROI:
    """Regions of interest for a specific poker site.
    All coordinates are relative to table window (normalized 0-1).
    """
    # Hero hole cards (x, y, w, h) as fraction of table size
    hero_card1: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    hero_card2: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    # Board cards
    board_card1: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    board_card2: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    board_card3: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    board_card4: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    board_card5: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    # Pot total text region
    pot_region: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    # Player stack regions (list of 6 for 6-max)
    stack_regions: list[tuple[float, float, float, float]] = field(default_factory=list)

    # Player name regions
    name_regions: list[tuple[float, float, float, float]] = field(default_factory=list)

    # Player bet regions
    bet_regions: list[tuple[float, float, float, float]] = field(default_factory=list)

    # Dealer button region (to detect positions)
    dealer_regions: list[tuple[float, float, float, float]] = field(default_factory=list)

    # CoinPoker stats regions (VPIP, PFR, etc. displayed on table)
    stats_regions: list[tuple[float, float, float, float]] = field(default_factory=list)

    # Player label anchor points (x, y) normalized — where to draw GTO labels
    # Each entry is (center_x, center_y) of the player's name area
    player_label_anchors: list[tuple[float, float]] = field(default_factory=list)


# Winamax 6-max table ROI (approximate, needs calibration with templates)
WINAMAX_ROI = SiteROI(
    hero_card1=(0.38, 0.72, 0.04, 0.08),
    hero_card2=(0.42, 0.72, 0.04, 0.08),
    board_card1=(0.30, 0.38, 0.04, 0.08),
    board_card2=(0.36, 0.38, 0.04, 0.08),
    board_card3=(0.42, 0.38, 0.04, 0.08),
    board_card4=(0.48, 0.38, 0.04, 0.08),
    board_card5=(0.54, 0.38, 0.04, 0.08),
    pot_region=(0.38, 0.32, 0.24, 0.05),
    stack_regions=[
        (0.05, 0.42, 0.10, 0.04),   # Seat 1 (left)
        (0.05, 0.18, 0.10, 0.04),   # Seat 2 (top-left)
        (0.45, 0.05, 0.10, 0.04),   # Seat 3 (top-right)
        (0.85, 0.18, 0.10, 0.04),   # Seat 4 (right)
        (0.85, 0.42, 0.10, 0.04),   # Seat 5 (bottom-right)
        (0.38, 0.78, 0.10, 0.04),   # Seat 6 (hero/bottom)
    ],
    name_regions=[
        (0.05, 0.38, 0.10, 0.04),
        (0.05, 0.14, 0.10, 0.04),
        (0.45, 0.01, 0.10, 0.04),
        (0.85, 0.14, 0.10, 0.04),
        (0.85, 0.38, 0.10, 0.04),
        (0.38, 0.74, 0.10, 0.04),
    ],
    bet_regions=[
        (0.18, 0.42, 0.08, 0.03),
        (0.18, 0.25, 0.08, 0.03),
        (0.45, 0.15, 0.08, 0.03),
        (0.74, 0.25, 0.08, 0.03),
        (0.74, 0.42, 0.08, 0.03),
        (0.45, 0.65, 0.08, 0.03),
    ],
    dealer_regions=[
        (0.16, 0.48, 0.03, 0.03),
        (0.16, 0.22, 0.03, 0.03),
        (0.43, 0.12, 0.03, 0.03),
        (0.80, 0.22, 0.03, 0.03),
        (0.80, 0.48, 0.03, 0.03),
        (0.50, 0.70, 0.03, 0.03),
    ],
)

# CoinPoker 6-max table ROI — measured from real 2x2 tiled screenshot.
# ALL coordinates normalized (0-1) relative to ONE table cell.
# Works for 1x1 (full window) and NxM grids (each cell = one table).
#
# CoinPoker 6-max seat layout:
#   Seat 0 = top-center          Seat 3 = bottom-left
#   Seat 1 = upper-left          Seat 4 = bottom-right
#   Seat 2 = upper-right         Seat 5 = hero (bottom-center)
#
# Measured from 2x2 screenshot: each cell ~526x392 px.
# Title bar ~3.5% of height. Green felt oval centered in cell.
COINPOKER_ROI = SiteROI(
    # Hero hole cards — just above hero name
    hero_card1=(0.43, 0.74, 0.04, 0.08),
    hero_card2=(0.48, 0.74, 0.04, 0.08),
    # Board cards — center felt, horizontal row, spacing ~0.075
    board_card1=(0.29, 0.41, 0.05, 0.10),
    board_card2=(0.36, 0.41, 0.05, 0.10),
    board_card3=(0.43, 0.41, 0.05, 0.10),
    board_card4=(0.50, 0.41, 0.05, 0.10),
    board_card5=(0.57, 0.41, 0.05, 0.10),
    # Pot text — above board cards
    pot_region=(0.41, 0.36, 0.16, 0.03),
    # Player stacks — tight boxes on the number below the name
    stack_regions=[
        (0.44, 0.23, 0.08, 0.025),  # Seat 0 — top-center
        (0.08, 0.31, 0.08, 0.025),  # Seat 1 — upper-left
        (0.82, 0.31, 0.08, 0.025),  # Seat 2 — upper-right
        (0.08, 0.71, 0.08, 0.025),  # Seat 3 — bottom-left
        (0.82, 0.71, 0.08, 0.025),  # Seat 4 — bottom-right
        (0.44, 0.91, 0.08, 0.025),  # Seat 5 — Hero
    ],
    # Player names — tight boxes on the name text
    name_regions=[
        (0.42, 0.20, 0.12, 0.025),  # Seat 0
        (0.06, 0.28, 0.12, 0.025),  # Seat 1
        (0.80, 0.28, 0.12, 0.025),  # Seat 2
        (0.06, 0.68, 0.12, 0.025),  # Seat 3
        (0.80, 0.68, 0.12, 0.025),  # Seat 4
        (0.42, 0.87, 0.12, 0.025),  # Seat 5
    ],
    # Bets — between each player and the pot center
    bet_regions=[
        (0.45, 0.28, 0.06, 0.025),  # Seat 0
        (0.22, 0.33, 0.06, 0.025),  # Seat 1
        (0.70, 0.33, 0.06, 0.025),  # Seat 2
        (0.22, 0.60, 0.06, 0.025),  # Seat 3
        (0.70, 0.60, 0.06, 0.025),  # Seat 4
        (0.45, 0.72, 0.06, 0.025),  # Seat 5
    ],
    # Dealer button — small D circle near each seat
    dealer_regions=[
        (0.55, 0.20, 0.02, 0.025),  # Seat 0
        (0.19, 0.26, 0.02, 0.025),  # Seat 1
        (0.79, 0.26, 0.02, 0.025),  # Seat 2
        (0.19, 0.65, 0.02, 0.025),  # Seat 3
        (0.79, 0.65, 0.02, 0.025),  # Seat 4
        (0.55, 0.85, 0.02, 0.025),  # Seat 5
    ],
    # CoinPoker stats — just below stack
    stats_regions=[
        (0.43, 0.255, 0.10, 0.03),  # Seat 0
        (0.07, 0.335, 0.10, 0.03),  # Seat 1
        (0.81, 0.335, 0.10, 0.03),  # Seat 2
        (0.07, 0.735, 0.10, 0.03),  # Seat 3
        (0.81, 0.735, 0.10, 0.03),  # Seat 4
        (0.43, 0.935, 0.10, 0.03),  # Seat 5
    ],
    # Label anchors — where to draw EXP./GEN. mini-labels (above name)
    player_label_anchors=[
        (0.49, 0.14),   # Seat 0
        (0.13, 0.22),   # Seat 1
        (0.86, 0.22),   # Seat 2
        (0.13, 0.62),   # Seat 3
        (0.86, 0.62),   # Seat 4
        (0.49, 0.81),   # Seat 5
    ],
)


# CoinPoker Heads-Up (2 players) ROI — normalized to cell.
# Seat 0 = Villain (top center), Seat 1 = Hero (bottom center)
COINPOKER_HU_ROI = SiteROI(
    hero_card1=(0.43, 0.74, 0.04, 0.08),
    hero_card2=(0.48, 0.74, 0.04, 0.08),
    board_card1=(0.29, 0.41, 0.05, 0.10),
    board_card2=(0.36, 0.41, 0.05, 0.10),
    board_card3=(0.43, 0.41, 0.05, 0.10),
    board_card4=(0.50, 0.41, 0.05, 0.10),
    board_card5=(0.57, 0.41, 0.05, 0.10),
    pot_region=(0.41, 0.36, 0.16, 0.03),
    stack_regions=[
        (0.44, 0.23, 0.08, 0.025),  # Seat 0 — Villain (top)
        (0.44, 0.91, 0.08, 0.025),  # Seat 1 — Hero (bottom)
    ],
    name_regions=[
        (0.42, 0.20, 0.12, 0.025),  # Seat 0 — Villain
        (0.42, 0.87, 0.12, 0.025),  # Seat 1 — Hero
    ],
    bet_regions=[
        (0.45, 0.30, 0.06, 0.025),  # Villain bet
        (0.45, 0.68, 0.06, 0.025),  # Hero bet
    ],
    dealer_regions=[
        (0.55, 0.20, 0.02, 0.025),  # Villain dealer
        (0.55, 0.85, 0.02, 0.025),  # Hero dealer
    ],
    stats_regions=[
        (0.43, 0.255, 0.10, 0.03),  # Villain stats
        (0.43, 0.935, 0.10, 0.03),  # Hero stats
    ],
    player_label_anchors=[
        (0.49, 0.14),   # Villain
        (0.49, 0.81),   # Hero
    ],
)


@dataclass
class SolverConfig:
    """TexasSolver configuration."""
    binary_path: str = "./TexasSolver"  # path to compiled binary
    max_iterations: int = 200           # fewer iterations = faster (<5s target)
    accuracy: float = 0.5               # 0.5% accuracy (vs 0.1% default) for speed
    thread_count: int = 4
    # Bet sizes (reduced tree for speed)
    flop_bet_sizes: str = "75"          # only 75% pot on flop
    turn_bet_sizes: str = "75"          # only 75% pot on turn
    river_bet_sizes: str = "75,150"     # 75% and 150% pot on river
    flop_raise_sizes: str = "2.5"       # 2.5x raise
    turn_raise_sizes: str = "2.5"
    river_raise_sizes: str = "2.5"
    allin_threshold: float = 1.5        # all-in if remaining stack < 1.5x pot


@dataclass
class Config:
    """Main application configuration."""
    site: str = "winamax"  # "winamax" or "coinpoker"
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    window: WindowConfig = field(default_factory=WindowConfig)
    solver: SolverConfig = field(default_factory=SolverConfig)
    debug_ocr: bool = False  # toggle with 'D' key
    # Grid layout for multi-table (set by launcher)
    grid_cols: int = 1   # e.g. 2 for "2x2"
    grid_rows: int = 1   # e.g. 2 for "2x2"
    grid_gap_x: int = 0        # horizontal gap between tables (pixels)
    grid_gap_y: int = 0        # vertical gap between tables (pixels)
    grid_width_pct: int = 100  # table width adjustment (80-120%)
    grid_height_pct: int = 100 # table height adjustment (80-120%)
    grid_shift_x: int = 0     # shift all tables left/right (pixels)
    grid_shift_y: int = 0     # shift all tables up/down (pixels)

    @property
    def site_roi(self) -> SiteROI:
        if self.site == "coinpoker":
            return COINPOKER_ROI
        return WINAMAX_ROI

    def get_roi_for_players(self, num_players: int) -> SiteROI:
        """Get ROI config based on number of detected players."""
        if self.site == "coinpoker":
            if num_players <= 2:
                return COINPOKER_HU_ROI
            return COINPOKER_ROI
        return WINAMAX_ROI
