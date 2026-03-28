"""Preflop range management for GTO analysis."""

from poker_analyzer.models.game_state import Position


# Standard 6-max preflop opening ranges (RFI - Raise First In)
# Format: comma-separated hand notation
# 's' = suited, 'o' = offsuit, pairs listed as 'AA', 'KK', etc.

RFI_RANGES = {
    Position.UTG: (
        "AA,KK,QQ,JJ,TT,99,88,77,"
        "AKs,AQs,AJs,ATs,A5s,A4s,"
        "KQs,KJs,KTs,"
        "QJs,QTs,"
        "JTs,"
        "T9s,"
        "98s,"
        "87s,"
        "76s,"
        "65s,"
        "AKo,AQo"
    ),
    Position.MP: (
        "AA,KK,QQ,JJ,TT,99,88,77,66,"
        "AKs,AQs,AJs,ATs,A9s,A5s,A4s,A3s,"
        "KQs,KJs,KTs,K9s,"
        "QJs,QTs,Q9s,"
        "JTs,J9s,"
        "T9s,T8s,"
        "98s,97s,"
        "87s,86s,"
        "76s,75s,"
        "65s,"
        "54s,"
        "AKo,AQo,AJo"
    ),
    Position.CO: (
        "AA,KK,QQ,JJ,TT,99,88,77,66,55,44,"
        "AKs,AQs,AJs,ATs,A9s,A8s,A7s,A6s,A5s,A4s,A3s,A2s,"
        "KQs,KJs,KTs,K9s,K8s,"
        "QJs,QTs,Q9s,Q8s,"
        "JTs,J9s,J8s,"
        "T9s,T8s,"
        "98s,97s,"
        "87s,86s,"
        "76s,75s,"
        "65s,64s,"
        "54s,53s,"
        "43s,"
        "AKo,AQo,AJo,ATo,"
        "KQo,KJo,"
        "QJo"
    ),
    Position.BTN: (
        "AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,"
        "AKs,AQs,AJs,ATs,A9s,A8s,A7s,A6s,A5s,A4s,A3s,A2s,"
        "KQs,KJs,KTs,K9s,K8s,K7s,K6s,K5s,"
        "QJs,QTs,Q9s,Q8s,Q7s,Q6s,"
        "JTs,J9s,J8s,J7s,"
        "T9s,T8s,T7s,"
        "98s,97s,96s,"
        "87s,86s,85s,"
        "76s,75s,74s,"
        "65s,64s,"
        "54s,53s,"
        "43s,"
        "32s,"
        "AKo,AQo,AJo,ATo,A9o,A8o,"
        "KQo,KJo,KTo,"
        "QJo,QTo,"
        "JTo,"
        "T9o"
    ),
    Position.SB: (
        "AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,"
        "AKs,AQs,AJs,ATs,A9s,A8s,A7s,A6s,A5s,A4s,A3s,A2s,"
        "KQs,KJs,KTs,K9s,K8s,K7s,K6s,K5s,K4s,"
        "QJs,QTs,Q9s,Q8s,Q7s,Q6s,"
        "JTs,J9s,J8s,J7s,"
        "T9s,T8s,T7s,"
        "98s,97s,96s,"
        "87s,86s,"
        "76s,75s,"
        "65s,64s,"
        "54s,53s,"
        "43s,"
        "AKo,AQo,AJo,ATo,A9o,A8o,A7o,"
        "KQo,KJo,KTo,"
        "QJo,QTo,"
        "JTo,J9o,"
        "T9o"
    ),
}

# BB defense range vs single raise (calling + 3betting)
BB_DEFEND = (
    "AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,"
    "AKs,AQs,AJs,ATs,A9s,A8s,A7s,A6s,A5s,A4s,A3s,A2s,"
    "KQs,KJs,KTs,K9s,K8s,K7s,K6s,K5s,K4s,K3s,K2s,"
    "QJs,QTs,Q9s,Q8s,Q7s,Q6s,Q5s,"
    "JTs,J9s,J8s,J7s,J6s,"
    "T9s,T8s,T7s,T6s,"
    "98s,97s,96s,95s,"
    "87s,86s,85s,"
    "76s,75s,74s,"
    "65s,64s,63s,"
    "54s,53s,52s,"
    "43s,42s,"
    "32s,"
    "AKo,AQo,AJo,ATo,A9o,A8o,A7o,A6o,A5o,A4o,"
    "KQo,KJo,KTo,K9o,K8o,"
    "QJo,QTo,Q9o,"
    "JTo,J9o,"
    "T9o,T8o,"
    "98o,97o,"
    "87o,86o,"
    "76o,75o,"
    "65o"
)

# 3-Bet ranges by position (vs UTG open)
THREE_BET_RANGES = {
    Position.MP: "AA,KK,QQ,AKs,AKo",
    Position.CO: "AA,KK,QQ,JJ,AKs,AQs,AKo",
    Position.BTN: "AA,KK,QQ,JJ,TT,AKs,AQs,AJs,AKo,AQo",
    Position.SB: "AA,KK,QQ,JJ,TT,99,AKs,AQs,AJs,ATs,A5s,A4s,KQs,AKo,AQo",
    Position.BB: "AA,KK,QQ,JJ,TT,99,AKs,AQs,AJs,ATs,A5s,A4s,KQs,KJs,AKo,AQo,AJo",
}


class RangeManager:
    """Manages preflop ranges for solver input."""

    def get_rfi_range(self, position: Position) -> str:
        """Get the RFI (Raise First In) range for a position."""
        return RFI_RANGES.get(position, "")

    def get_defend_range(self, position: Position) -> str:
        """Get the defend range (call + 3bet) for BB."""
        if position == Position.BB:
            return BB_DEFEND
        return ""

    def get_3bet_range(self, position: Position) -> str:
        """Get the 3-bet range for a position."""
        return THREE_BET_RANGES.get(position, "")

    def get_ranges_for_spot(
        self,
        oop_position: Position,
        ip_position: Position,
        is_3bet_pot: bool = False,
    ) -> tuple[str, str]:
        """Get OOP and IP ranges for a given spot.

        Args:
            oop_position: Out-of-position player's position.
            ip_position: In-position player's position.
            is_3bet_pot: Whether this is a 3-bet pot.

        Returns:
            (oop_range, ip_range) as range strings.
        """
        if is_3bet_pot:
            # 3-bet pot: 3bettor range vs caller range
            oop_range = self.get_3bet_range(oop_position)
            ip_range = self.get_rfi_range(ip_position)
        else:
            # Single raised pot
            if ip_position in RFI_RANGES:
                ip_range = self.get_rfi_range(ip_position)
            else:
                ip_range = self.get_rfi_range(Position.CO)  # default

            if oop_position == Position.BB:
                oop_range = self.get_defend_range(Position.BB)
            elif oop_position in RFI_RANGES:
                oop_range = self.get_rfi_range(oop_position)
            else:
                oop_range = BB_DEFEND  # default

        return oop_range, ip_range

    def range_to_solver_format(self, range_str: str) -> str:
        """Convert range string to TexasSolver input format.

        TexasSolver expects ranges like:
        AA,KK,QQ,JJ,AKs,AKo:0.5 (with optional weights)
        """
        # Clean up — remove whitespace and trailing commas
        cleaned = range_str.replace(" ", "").replace("\n", "").strip(",")
        return cleaned
