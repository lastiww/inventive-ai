"""
Notifications — console colorée et Telegram (optionnel).
"""
import logging
from typing import Optional

import httpx

from .analyzer import DealResult

logger = logging.getLogger(__name__)

# Codes ANSI pour la console
_RESET = "\033[0m"
_BOLD = "\033[1m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_CYAN = "\033[96m"
_DIM = "\033[2m"


def _score_color(score: int) -> str:
    if score >= 75:
        return _GREEN
    if score >= 55:
        return _YELLOW
    return _RED


def _bar(score: int, width: int = 20) -> str:
    filled = int(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


def format_deal_console(result: DealResult) -> str:
    """Formate un DealResult pour affichage console."""
    l = result.listing
    color = _score_color(result.deal_score)
    lines = [
        f"\n{_BOLD}{color}{'─'*60}{_RESET}",
        f"{_BOLD}{color}[Score {result.deal_score}/100] {_bar(result.deal_score)}{_RESET}",
        f"{_BOLD}{l.title}{_RESET}",
        f"  Prix demandé : {_BOLD}{_GREEN}{l.price:,} €{_RESET}",
    ]

    if result.market_price > 0:
        gap_str = f"{result.price_gap_pct:+.1f}%"
        gap_color = _GREEN if result.price_gap_pct > 0 else _RED
        lines.append(
            f"  Prix marché  : {result.market_price:,.0f} €  "
            f"({gap_color}{gap_str}{_RESET}) — {result.sample_size} annonces"
        )
        lines.append(
            f"  Revente est. : {result.estimated_resale:,.0f} €  "
            f"→ bénéfice {_BOLD}{result.estimated_profit:+,.0f} €{_RESET}"
        )

    details = []
    if l.brand:
        details.append(l.brand.capitalize())
    if l.model:
        details.append(l.model.capitalize())
    if l.year:
        details.append(str(l.year))
    if l.mileage:
        details.append(f"{l.mileage:,} km")
    if l.fuel:
        details.append(l.fuel)
    if l.gearbox:
        details.append(l.gearbox)
    if details:
        lines.append(f"  Détails      : {' | '.join(details)}")

    loc = " — ".join(filter(None, [l.location_city, l.location_dept]))
    if loc:
        lines.append(f"  Localisation : {loc}")

    lines.append(f"  Vendeur      : {l.seller_type or 'inconnu'}")

    if result.reasons:
        lines.append(f"  {_DIM}Raisons :")
        for r in result.reasons[:4]:
            lines.append(f"    • {r}{_RESET}")

    lines.append(f"  {_CYAN}Lien : {l.url}{_RESET}")
    lines.append(f"{color}{'─'*60}{_RESET}")
    return "\n".join(lines)


def print_summary(results: list[DealResult], total_scanned: int):
    """Affiche un résumé en console."""
    deals = [r for r in results if r.is_deal]
    worth = [r for r in results if not r.is_deal and r.deal_score >= 40]

    print(f"\n{_BOLD}{'═'*60}{_RESET}")
    print(f"{_BOLD}  RÉSULTATS DU SCAN — {total_scanned} annonces analysées{_RESET}")
    print(f"{'═'*60}{_RESET}")
    print(f"  Bonnes affaires (score ≥ seuil) : {_GREEN}{len(deals)}{_RESET}")
    print(f"  À surveiller (score ≥ 40)       : {_YELLOW}{len(worth)}{_RESET}")

    if deals:
        print(f"\n{_BOLD}{_GREEN}  MEILLEURES AFFAIRES :{_RESET}")
        for r in deals[:10]:
            print(format_deal_console(r))

    if worth and not deals:
        print(f"\n{_BOLD}{_YELLOW}  À SURVEILLER :{_RESET}")
        for r in worth[:5]:
            print(format_deal_console(r))


class TelegramNotifier:
    """Envoie des alertes via un bot Telegram."""

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self._base = f"https://api.telegram.org/bot{token}"

    def send(self, result: DealResult):
        l = result.listing
        gap_str = f"{result.price_gap_pct:+.1f}%" if result.market_price else "N/A"
        profit_str = f"{result.estimated_profit:+,.0f} €" if result.estimated_profit else "N/A"

        text = (
            f"🚗 *{l.title}*\n"
            f"💰 Prix : *{l.price:,} €* (marché : {result.market_price:,.0f} €, {gap_str})\n"
            f"📈 Bénéfice estimé : *{profit_str}*\n"
            f"⭐ Score : *{result.deal_score}/100*\n"
            f"📍 {l.location_city} ({l.location_dept})\n"
            f"🔗 [Voir l'annonce]({l.url})"
        )

        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(
                    f"{self._base}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": False,
                    },
                )
                resp.raise_for_status()
                logger.info("Notification Telegram envoyée pour l'annonce %s", l.ad_id)
        except Exception as exc:
            logger.warning("Erreur Telegram : %s", exc)

    def send_batch(self, results: list[DealResult]):
        for r in results:
            self.send(r)


def get_notifier(token: str, chat_id: str) -> Optional[TelegramNotifier]:
    if token and chat_id:
        return TelegramNotifier(token, chat_id)
    return None
