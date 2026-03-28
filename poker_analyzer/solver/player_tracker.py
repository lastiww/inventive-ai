"""Player stats tracker for exploitative analysis."""

import json
from pathlib import Path

from poker_analyzer.models.game_state import PlayerStats


STATS_FILE = Path(__file__).parent / "player_stats.json"


class PlayerTracker:
    """Tracks player statistics over time for exploitative play.

    On CoinPoker: reads stats directly from the table via OCR.
    On Winamax: accumulates stats manually from observed actions.
    """

    def __init__(self):
        self._players: dict[str, PlayerStats] = {}
        self._load()

    def get_stats(self, player_name: str) -> PlayerStats | None:
        """Get tracked stats for a player."""
        return self._players.get(player_name)

    def update_from_ocr(self, player_name: str, stats: PlayerStats):
        """Update player stats from CoinPoker OCR data."""
        self._players[player_name] = stats
        self._save()

    def record_action(
        self,
        player_name: str,
        action: str,
        is_preflop: bool = True,
        facing_cbet: bool = False,
        facing_raise: bool = False,
    ):
        """Record an observed action to update stats manually.

        Used for Winamax where stats aren't displayed on the table.
        """
        if player_name not in self._players:
            self._players[player_name] = PlayerStats()

        stats = self._players[player_name]
        stats.hands_played += 1

        if is_preflop:
            if action in ("call", "raise", "allin"):
                # VPIP: voluntarily put money in pot
                new_vpip_hands = stats.vpip * (stats.hands_played - 1) / 100 + 1
                stats.vpip = (new_vpip_hands / stats.hands_played) * 100

                if action in ("raise", "allin"):
                    # PFR: preflop raise
                    new_pfr_hands = stats.pfr * (stats.hands_played - 1) / 100 + 1
                    stats.pfr = (new_pfr_hands / stats.hands_played) * 100
            else:
                # Fold or check — update running averages
                new_vpip_hands = stats.vpip * (stats.hands_played - 1) / 100
                stats.vpip = (new_vpip_hands / stats.hands_played) * 100

                new_pfr_hands = stats.pfr * (stats.hands_played - 1) / 100
                stats.pfr = (new_pfr_hands / stats.hands_played) * 100

            if facing_raise and action in ("raise", "allin"):
                # 3-bet
                new_3bet = stats.three_bet * (stats.hands_played - 1) / 100 + 1
                stats.three_bet = (new_3bet / stats.hands_played) * 100

        if facing_cbet and action == "fold":
            # Fold to c-bet
            new_ftcb = stats.fold_to_cbet * (stats.hands_played - 1) / 100 + 1
            stats.fold_to_cbet = (new_ftcb / stats.hands_played) * 100

        self._save()

    def get_all_players(self) -> dict[str, PlayerStats]:
        """Get all tracked player stats."""
        return self._players.copy()

    def has_enough_data(self, player_name: str, min_hands: int = 20) -> bool:
        """Check if we have enough data for meaningful exploitative play."""
        stats = self._players.get(player_name)
        if stats is None:
            return False
        return stats.hands_played >= min_hands

    def get_deviation_summary(self, player_name: str) -> dict[str, str]:
        """Get a summary of player's deviations from GTO averages.

        GTO approximations for 6-max:
        - VPIP: ~22-27%
        - PFR: ~18-23%
        - 3-Bet: ~7-10%
        - Fold to CBet: ~40-50%
        """
        stats = self._players.get(player_name)
        if stats is None:
            return {}

        deviations = {}

        if stats.vpip > 30:
            deviations["vpip"] = f"Loose ({stats.vpip:.0f}% vs GTO ~25%)"
        elif stats.vpip < 20:
            deviations["vpip"] = f"Tight ({stats.vpip:.0f}% vs GTO ~25%)"

        if stats.pfr > 25:
            deviations["pfr"] = f"Aggressive ({stats.pfr:.0f}% vs GTO ~20%)"
        elif stats.pfr < 15:
            deviations["pfr"] = f"Passive ({stats.pfr:.0f}% vs GTO ~20%)"

        if stats.fold_to_cbet > 60:
            deviations["fold_to_cbet"] = f"Overfolds ({stats.fold_to_cbet:.0f}% vs GTO ~45%)"
        elif stats.fold_to_cbet < 35:
            deviations["fold_to_cbet"] = f"Underfolds ({stats.fold_to_cbet:.0f}% vs GTO ~45%)"

        if stats.three_bet > 12:
            deviations["three_bet"] = f"3bets a lot ({stats.three_bet:.0f}% vs GTO ~8%)"
        elif stats.three_bet < 5:
            deviations["three_bet"] = f"Rarely 3bets ({stats.three_bet:.0f}% vs GTO ~8%)"

        return deviations

    def _load(self):
        """Load player stats from disk."""
        if STATS_FILE.exists():
            try:
                with open(STATS_FILE) as f:
                    data = json.load(f)
                for name, vals in data.items():
                    self._players[name] = PlayerStats(**vals)
                print(f"[TRACKER] Loaded stats for {len(self._players)} players")
            except Exception as e:
                print(f"[TRACKER] Load error: {e}")

    def _save(self):
        """Save player stats to disk."""
        data = {}
        for name, stats in self._players.items():
            data[name] = {
                "vpip": stats.vpip,
                "pfr": stats.pfr,
                "three_bet": stats.three_bet,
                "fold_to_cbet": stats.fold_to_cbet,
                "agg_factor": stats.agg_factor,
                "hands_played": stats.hands_played,
            }

        STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATS_FILE, "w") as f:
            json.dump(data, f, indent=2)
