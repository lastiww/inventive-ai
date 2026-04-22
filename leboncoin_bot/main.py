"""
Bot LeBonCoin — point d'entrée principal.

Usage :
    python -m leboncoin_bot                          # scan unique, profil citadines
    python -m leboncoin_bot --profil compactes       # profil différent
    python -m leboncoin_bot --loop 300               # scan toutes les 5 min
    python -m leboncoin_bot --marques peugeot renault --prix-max 8000
    python -m leboncoin_bot --deals                  # affiche les meilleurs deals en base
    python -m leboncoin_bot --telegram-token TOK --telegram-chat-id CID
"""
import argparse
import logging
import sys
import time
from datetime import datetime

from .analyzer import DealResult, PriceAnalyzer
from .config import (
    DEFAULT_ANALYSIS,
    DEFAULT_BOT,
    PROFIL_CITADINES,
    PROFIL_COMPACTES,
    PROFIL_PREMIUM,
    PROFIL_SUV_ABORDABLES,
    AnalysisConfig,
    BotConfig,
    SearchCriteria,
)
from .database import Database
from .notifier import TelegramNotifier, get_notifier, print_summary
from .scraper import CarListing, LeBonCoinScraper

PROFILS = {
    "citadines": PROFIL_CITADINES,
    "compactes": PROFIL_COMPACTES,
    "suv": PROFIL_SUV_ABORDABLES,
    "premium": PROFIL_PREMIUM,
}


def setup_logging(log_file: str, verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


def run_scan(
    criteria: SearchCriteria,
    bot_cfg: BotConfig,
    analysis_cfg: AnalysisConfig,
    db: Database,
    notifier: TelegramNotifier | None,
) -> list[DealResult]:
    """Lance un cycle de scan complet."""
    logger = logging.getLogger(__name__)
    analyzer = PriceAnalyzer(analysis_cfg)
    all_results: list[DealResult] = []
    new_count = 0

    logger.info("Démarrage du scan — %s", datetime.now().strftime("%d/%m/%Y %H:%M"))

    with LeBonCoinScraper(bot_cfg) as scraper:
        listings = scraper.search(criteria)
        logger.info("%d annonces récupérées au total", len(listings))

        for i, listing in enumerate(listings, 1):
            is_new = db.upsert_listing(listing)
            if is_new:
                new_count += 1

            # Récupère l'échantillon marché pour cette voiture
            sample = scraper.get_market_sample(listing.brand, listing.model, listing.year)

            result = analyzer.analyze(listing, sample)
            db.save_deal_result(result)
            all_results.append(result)

            if result.is_deal and is_new:
                logger.info(
                    "  ★ DEAL #%d — %s — %d€ (score %d, écart %+.0f%%)",
                    i, listing.title, listing.price,
                    result.deal_score, result.price_gap_pct,
                )
                if notifier:
                    notifier.send(result)
            elif i % 10 == 0:
                logger.debug("  Progress %d/%d…", i, len(listings))

    logger.info(
        "Scan terminé — %d nouvelles annonces, %d deals détectés",
        new_count,
        len([r for r in all_results if r.is_deal]),
    )
    return all_results


def show_best_deals(db: Database, limit: int = 20):
    deals = db.get_best_deals(limit)
    if not deals:
        print("Aucune bonne affaire enregistrée en base.")
        return

    print(f"\n{'═'*65}")
    print(f"  MEILLEURES AFFAIRES EN BASE ({len(deals)} résultats)")
    print(f"{'═'*65}")
    for d in deals:
        print(
            f"  [{d['deal_score']:3}/100] {d['title'][:40]:<40} "
            f"{d.get('price', '?'):>6}€  +{d['price_gap_pct']:.0f}%  "
            f"profit ~{d['estimated_profit']:.0f}€"
        )
        print(f"           {d['url']}")
    stats = db.get_stats()
    print(f"\n  Stats : {stats['total_listings']} annonces, {stats['total_deals']} deals")


def build_criteria_from_args(args: argparse.Namespace) -> SearchCriteria:
    base = PROFILS.get(args.profil, PROFIL_CITADINES)

    if args.marques:
        base.brands = args.marques
    if args.modeles:
        base.models = args.modeles
    if args.prix_min is not None:
        base.price_min = args.prix_min
    if args.prix_max is not None:
        base.price_max = args.prix_max
    if args.annee_min is not None:
        base.year_min = args.annee_min
    if args.km_max is not None:
        base.mileage_max = args.km_max
    if args.departements:
        base.departments = args.departements

    return base


def main():
    parser = argparse.ArgumentParser(
        description="Bot LeBonCoin — détecte les voitures sous-cotées pour revente"
    )

    # Critères de recherche
    parser.add_argument("--profil", default="citadines",
                        choices=list(PROFILS.keys()),
                        help="Profil de recherche prédéfini")
    parser.add_argument("--marques", nargs="+", metavar="MARQUE",
                        help="Marques à rechercher (ex: peugeot renault)")
    parser.add_argument("--modeles", nargs="+", metavar="MODELE",
                        help="Modèles à rechercher (ex: 208 clio)")
    parser.add_argument("--prix-min", type=int, metavar="EUR")
    parser.add_argument("--prix-max", type=int, metavar="EUR")
    parser.add_argument("--annee-min", type=int, metavar="ANNEE")
    parser.add_argument("--km-max", type=int, metavar="KM")
    parser.add_argument("--departements", nargs="+", metavar="DEPT",
                        help="Codes département (ex: 75 92 93)")

    # Comportement bot
    parser.add_argument("--loop", type=int, metavar="SECONDES",
                        help="Mode boucle : scan toutes les N secondes")
    parser.add_argument("--seuil", type=float, default=20.0,
                        help="Seuil %% sous le marché pour alerter (défaut: 20)")
    parser.add_argument("--score-min", type=int, default=60,
                        help="Score minimum pour une alerte (défaut: 60)")
    parser.add_argument("--pages", type=int, default=5,
                        help="Nombre de pages à scraper (défaut: 5)")

    # Telegram
    parser.add_argument("--telegram-token", default="",
                        help="Token du bot Telegram")
    parser.add_argument("--telegram-chat-id", default="",
                        help="Chat ID Telegram")

    # Actions
    parser.add_argument("--deals", action="store_true",
                        help="Affiche les meilleurs deals en base et quitte")
    parser.add_argument("--db", default="leboncoin_cars.db",
                        help="Chemin vers la base SQLite")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    setup_logging("leboncoin_bot.log", args.verbose)
    logger = logging.getLogger(__name__)

    db = Database(args.db)

    if args.deals:
        show_best_deals(db)
        return

    criteria = build_criteria_from_args(args)
    bot_cfg = BotConfig(
        max_pages=args.pages,
        telegram_enabled=bool(args.telegram_token),
        telegram_token=args.telegram_token,
        telegram_chat_id=args.telegram_chat_id,
    )
    analysis_cfg = AnalysisConfig(
        deal_threshold_pct=args.seuil,
        min_alert_score=args.score_min,
    )
    notifier = get_notifier(args.telegram_token, args.telegram_chat_id)

    if args.loop:
        logger.info("Mode boucle : scan toutes les %d secondes", args.loop)
        while True:
            try:
                results = run_scan(criteria, bot_cfg, analysis_cfg, db, notifier)
                print_summary(results, len(results))
            except KeyboardInterrupt:
                logger.info("Arrêt demandé.")
                break
            except Exception as exc:
                logger.error("Erreur lors du scan : %s", exc, exc_info=True)

            logger.info("Prochain scan dans %d secondes…", args.loop)
            try:
                time.sleep(args.loop)
            except KeyboardInterrupt:
                break
    else:
        results = run_scan(criteria, bot_cfg, analysis_cfg, db, notifier)
        print_summary(results, len(results))


if __name__ == "__main__":
    main()
