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

# CoinPoker 6-max table ROI — calibrated from real CoinPoker screenshot
# Seat order: 0=SB(bottom-left), 1=BB(left), 2=top-center,
#             3=top-right, 4=bottom-right, 5=hero(bottom-center)
COINPOKER_ROI = SiteROI(
    hero_card1=(0.33, 0.73, 0.05, 0.09),
    hero_card2=(0.38, 0.73, 0.05, 0.09),
    board_card1=(0.30, 0.42, 0.04, 0.08),
    board_card2=(0.36, 0.42, 0.04, 0.08),
    board_card3=(0.42, 0.42, 0.04, 0.08),
    board_card4=(0.48, 0.42, 0.04, 0.08),
    board_card5=(0.54, 0.42, 0.04, 0.08),
    pot_region=(0.33, 0.50, 0.20, 0.04),
    stack_regions=[
        (0.03, 0.68, 0.10, 0.03),   # Seat 0 — SB (GTAmoves)
        (0.03, 0.46, 0.10, 0.03),   # Seat 1 — BB (Pimylimpy)
        (0.30, 0.38, 0.10, 0.03),   # Seat 2 — top center (DobleZero)
        (0.82, 0.46, 0.10, 0.03),   # Seat 3 — top right (GR3N4DI3R)
        (0.82, 0.68, 0.10, 0.03),   # Seat 4 — bottom right (Thestral4ik)
        (0.30, 0.83, 0.10, 0.03),   # Seat 5 — Hero (VdrNoMercy)
    ],
    name_regions=[
        (0.03, 0.65, 0.10, 0.03),   # Seat 0 — SB
        (0.03, 0.43, 0.10, 0.03),   # Seat 1 — BB
        (0.30, 0.35, 0.10, 0.03),   # Seat 2 — top center
        (0.82, 0.43, 0.10, 0.03),   # Seat 3 — top right
        (0.82, 0.65, 0.10, 0.03),   # Seat 4 — bottom right
        (0.30, 0.80, 0.10, 0.03),   # Seat 5 — Hero
    ],
    bet_regions=[
        (0.17, 0.65, 0.08, 0.03),
        (0.17, 0.46, 0.08, 0.03),
        (0.42, 0.32, 0.08, 0.03),
        (0.72, 0.46, 0.08, 0.03),
        (0.72, 0.65, 0.08, 0.03),
        (0.42, 0.75, 0.08, 0.03),
    ],
    dealer_regions=[
        (0.14, 0.70, 0.02, 0.02),
        (0.14, 0.48, 0.02, 0.02),
        (0.42, 0.37, 0.02, 0.02),
        (0.80, 0.48, 0.02, 0.02),
        (0.80, 0.70, 0.02, 0.02),
        (0.42, 0.78, 0.02, 0.02),
    ],
    stats_regions=[
        (0.03, 0.71, 0.10, 0.05),
        (0.03, 0.49, 0.10, 0.05),
        (0.30, 0.41, 0.10, 0.05),
        (0.82, 0.49, 0.10, 0.05),
        (0.82, 0.71, 0.10, 0.05),
        (0.30, 0.86, 0.10, 0.05),
    ],
    # Player label anchor points — where to draw COMP./GEN. labels
    # (center_x, center_y) normalized, positioned near each player's name
    player_label_anchors=[
        (0.08, 0.63),   # Seat 0 — SB (GTAmoves) — label above name
        (0.08, 0.41),   # Seat 1 — BB (Pimylimpy)
        (0.35, 0.33),   # Seat 2 — top center (DobleZero)
        (0.87, 0.41),   # Seat 3 — top right (GR3N4DI3R)
        (0.87, 0.63),   # Seat 4 — bottom right (Thestral4ik)
        (0.35, 0.78),   # Seat 5 — Hero (VdrNoMercy)
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

    @property
    def site_roi(self) -> SiteROI:
        if self.site == "coinpoker":
            return COINPOKER_ROI
        return WINAMAX_ROI
