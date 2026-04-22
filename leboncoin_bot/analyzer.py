"""
Analyseur de prix — détecte les bonnes affaires à acheter pour revendre.

Algorithme :
1. Pour chaque annonce trouvée, récupère un échantillon d'annonces similaires
   (même marque, modèle, ±2 ans).
2. Calcule le prix médian du marché sur cet échantillon.
3. Calcule l'écart entre le prix affiché et le prix marché.
4. Attribue un score global (0-100) pondérant : écart de prix, kilométrage,
   ancienneté et type de vendeur.
5. Génère des recommandations d'achat/revente avec marge estimée.
"""
import logging
import statistics
from dataclasses import dataclass
from typing import Optional

from .config import AnalysisConfig
from .scraper import CarListing

logger = logging.getLogger(__name__)

CURRENT_YEAR = 2026


@dataclass
class DealResult:
    """Résultat d'analyse pour une annonce."""
    listing: CarListing
    market_price: float          # Prix médian du marché
    price_gap_pct: float         # % en-dessous du marché (positif = bonne affaire)
    estimated_resale: float      # Prix de revente estimé
    estimated_profit: float      # Bénéfice brut estimé
    deal_score: int              # Score 0-100
    sample_size: int             # Nombre d'annonces similaires utilisées
    is_deal: bool                # Passe le seuil minimal ?
    reasons: list[str]           # Explications humaines du score


def _median_price(listings: list[CarListing]) -> Optional[float]:
    prices = [l.price for l in listings if 500 < l.price < 100_000]
    if not prices:
        return None
    return statistics.median(prices)


def _score_price_gap(gap_pct: float) -> float:
    """Score 0-100 basé sur l'écart au prix marché."""
    if gap_pct <= 0:
        return 0.0
    if gap_pct >= 40:
        return 100.0
    return gap_pct / 40 * 100


def _score_mileage(mileage: int, year: int) -> float:
    """Score 0-100 : moins de km = mieux. Référence : 15 000 km/an."""
    if mileage <= 0 or year <= 0:
        return 50.0
    age = max(CURRENT_YEAR - year, 1)
    avg_mileage = age * 15_000
    ratio = mileage / avg_mileage  # 1.0 = dans la moyenne
    if ratio <= 0.5:
        return 100.0
    if ratio >= 2.0:
        return 0.0
    return max(0.0, (2.0 - ratio) / 1.5 * 100)


def _score_age(year: int) -> float:
    """Score 0-100 : voiture récente = mieux."""
    if year <= 0:
        return 50.0
    age = CURRENT_YEAR - year
    if age <= 3:
        return 100.0
    if age >= 15:
        return 0.0
    return (15 - age) / 12 * 100


def _score_seller(seller_type: str) -> float:
    """Les particuliers offrent souvent de meilleures affaires que les pros."""
    if seller_type.lower() in ("private", "particulier", "part"):
        return 100.0
    return 40.0


def _build_reasons(
    gap_pct: float,
    mileage: int,
    year: int,
    seller_type: str,
    sample_size: int,
    market_price: float,
) -> list[str]:
    reasons = []

    if gap_pct >= 30:
        reasons.append(f"Prix {gap_pct:.0f}% en-dessous du marché ({market_price:.0f}€) — très rare")
    elif gap_pct >= 20:
        reasons.append(f"Prix {gap_pct:.0f}% sous le marché — excellente affaire")
    elif gap_pct >= 10:
        reasons.append(f"Prix {gap_pct:.0f}% sous le marché — bonne affaire")
    elif gap_pct > 0:
        reasons.append(f"Prix légèrement sous le marché ({gap_pct:.0f}%)")
    else:
        reasons.append(f"Prix dans/au-dessus du marché ({abs(gap_pct):.0f}% de trop)")

    if year > 0:
        age = CURRENT_YEAR - year
        if mileage > 0:
            km_per_year = mileage / max(age, 1)
            if km_per_year < 10_000:
                reasons.append(f"Faible kilométrage ({km_per_year:.0f} km/an)")
            elif km_per_year > 25_000:
                reasons.append(f"Kilométrage élevé ({km_per_year:.0f} km/an)")

        if age <= 4:
            reasons.append(f"Véhicule récent ({year})")
        elif age >= 12:
            reasons.append(f"Véhicule ancien ({year})")

    if seller_type.lower() in ("private", "particulier", "part"):
        reasons.append("Vendeur particulier (négo possible)")
    else:
        reasons.append("Vendeur professionnel")

    if sample_size < 5:
        reasons.append(f"Prix marché peu fiable (seulement {sample_size} annonces similaires)")
    else:
        reasons.append(f"Prix marché basé sur {sample_size} annonces similaires")

    return reasons


class PriceAnalyzer:
    """Analyse les annonces et détecte les bonnes affaires."""

    def __init__(self, config: AnalysisConfig):
        self.config = config

    def analyze(
        self,
        listing: CarListing,
        market_sample: list[CarListing],
    ) -> DealResult:
        """
        Analyse une annonce par rapport à un échantillon de marché.
        """
        # Exclure l'annonce elle-même de l'échantillon
        sample = [l for l in market_sample if l.ad_id != listing.ad_id]

        market_price = _median_price(sample)
        sample_size = len([l for l in sample if 500 < l.price < 100_000])

        if market_price is None or sample_size < 1:
            # Impossible d'estimer le marché — score neutre
            return DealResult(
                listing=listing,
                market_price=0.0,
                price_gap_pct=0.0,
                estimated_resale=listing.price * 1.10,
                estimated_profit=0.0,
                deal_score=0,
                sample_size=0,
                is_deal=False,
                reasons=["Pas assez de données pour estimer le prix marché"],
            )

        price_gap_pct = (market_price - listing.price) / market_price * 100

        # Score composite pondéré
        s_price = _score_price_gap(price_gap_pct)
        s_mileage = _score_mileage(listing.mileage, listing.year)
        s_age = _score_age(listing.year)
        s_seller = _score_seller(listing.seller_type)

        cfg = self.config
        raw_score = (
            s_price * cfg.weight_price_gap
            + s_mileage * cfg.weight_mileage
            + s_age * cfg.weight_age
            + s_seller * cfg.weight_seller
        )
        deal_score = min(100, max(0, int(raw_score)))

        # Estimation de la revente au prix marché (avec légère décote pour vite vendre)
        resale_factor = 1.0 - (price_gap_pct / 200)   # on revend ~à prix marché
        estimated_resale = market_price * 0.95          # 5% de décote pour vendre vite
        estimated_profit = estimated_resale - listing.price

        reasons = _build_reasons(
            price_gap_pct, listing.mileage, listing.year,
            listing.seller_type, sample_size, market_price,
        )

        is_deal = (
            deal_score >= cfg.min_alert_score
            and price_gap_pct >= cfg.deal_threshold_pct
            and sample_size >= cfg.min_sample_size
        )

        return DealResult(
            listing=listing,
            market_price=round(market_price, 0),
            price_gap_pct=round(price_gap_pct, 1),
            estimated_resale=round(estimated_resale, 0),
            estimated_profit=round(estimated_profit, 0),
            deal_score=deal_score,
            sample_size=sample_size,
            is_deal=is_deal,
            reasons=reasons,
        )

    def rank_deals(self, results: list[DealResult]) -> list[DealResult]:
        """Trie les résultats par score décroissant, ne garde que les deals."""
        deals = [r for r in results if r.is_deal]
        return sorted(deals, key=lambda r: r.deal_score, reverse=True)

    def filter_worth_checking(self, results: list[DealResult]) -> list[DealResult]:
        """Garde toutes les annonces avec un score >= 40, même sans seuil de prix."""
        return sorted(
            [r for r in results if r.deal_score >= 40],
            key=lambda r: r.deal_score,
            reverse=True,
        )
