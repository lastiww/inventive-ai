"""
Scraper LeBonCoin — interroge l'API publique de recherche d'annonces.
"""
import json
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from .config import BotConfig, SearchCriteria

logger = logging.getLogger(__name__)

# Clé API utilisée par le site LeBonCoin (publique, visible dans les DevTools)
LBC_API_KEY = "ba0c2dad52b3565c9eef4f94457fd46f"
LBC_SEARCH_URL = "https://api.leboncoin.fr/api/adfinder/v1/search"
LBC_AD_BASE_URL = "https://www.leboncoin.fr/voitures/"

CATEGORY_CAR = "2"

FUEL_MAP = {
    "essence": "1",
    "diesel": "2",
    "hybride": "3",
    "electrique": "5",
    "gpl": "4",
}

GEARBOX_MAP = {
    "manuelle": "1",
    "automatique": "2",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://www.leboncoin.fr",
    "Referer": "https://www.leboncoin.fr/",
    "api_key": LBC_API_KEY,
    "Content-Type": "application/json",
}


@dataclass
class CarListing:
    """Une annonce voiture LeBonCoin."""
    ad_id: str
    title: str
    price: int
    url: str
    brand: str = ""
    model: str = ""
    year: int = 0
    mileage: int = 0
    fuel: str = ""
    gearbox: str = ""
    doors: int = 0
    seller_type: str = ""   # "pro" ou "private"
    location_city: str = ""
    location_dept: str = ""
    published_at: str = ""
    images: list[str] = field(default_factory=list)
    description: str = ""
    # Rempli par l'analyseur
    market_price: float = 0.0
    price_gap_pct: float = 0.0
    deal_score: int = 0


def _build_search_payload(criteria: SearchCriteria, offset: int = 0, limit: int = 35) -> dict:
    """Construit le corps JSON pour l'API LeBonCoin."""
    enums: dict = {"ad_type": ["offer"]}
    ranges: dict = {}
    keywords: dict = {}

    # Prix
    price_range: dict = {}
    if criteria.price_min:
        price_range["min"] = criteria.price_min
    if criteria.price_max:
        price_range["max"] = criteria.price_max
    if price_range:
        ranges["price"] = price_range

    # Kilométrage
    if criteria.mileage_max:
        ranges["mileage"] = {"max": criteria.mileage_max}

    # Année
    year_range: dict = {}
    if criteria.year_min:
        year_range["min"] = criteria.year_min
    if criteria.year_max:
        year_range["max"] = criteria.year_max
    if year_range:
        ranges["regdate"] = year_range

    # Carburant
    if criteria.fuel_types:
        fuel_ids = [FUEL_MAP[f] for f in criteria.fuel_types if f in FUEL_MAP]
        if fuel_ids:
            enums["fuel"] = fuel_ids

    # Boîte de vitesses
    if criteria.gearbox and criteria.gearbox in GEARBOX_MAP:
        enums["gearbox"] = [GEARBOX_MAP[criteria.gearbox]]

    # Marques / modèles — passés en keyword car l'API les accepte mieux ainsi
    brand_parts = criteria.brands + criteria.models
    if brand_parts:
        keywords["text"] = " ".join(brand_parts[:3])   # max 3 termes

    location: dict = {}
    if criteria.departments:
        location["locations"] = [
            {"locationType": "department", "departmentId": d}
            for d in criteria.departments
        ]
    elif criteria.regions:
        location["locations"] = [
            {"locationType": "region", "regionId": r}
            for r in criteria.regions
        ]

    payload: dict = {
        "limit": limit,
        "offset": offset,
        "filters": {
            "category": {"id": CATEGORY_CAR},
            "enums": enums,
            "ranges": ranges,
            "keywords": keywords,
        },
        "sort_by": "time",
        "sort_order": "desc",
    }
    if location:
        payload["filters"]["location"] = location

    return payload


def _parse_listing(ad: dict) -> Optional[CarListing]:
    """Extrait les données pertinentes d'une annonce brute."""
    try:
        ad_id = str(ad.get("list_id", ""))
        price_data = ad.get("price", [])
        price = int(price_data[0]) if price_data else 0
        if price <= 0:
            return None

        title = ad.get("subject", "")
        url = LBC_AD_BASE_URL + ad_id + "/"

        attrs: dict = {}
        for attr in ad.get("attributes", []):
            attrs[attr.get("key", "")] = attr.get("value", "")

        images = [
            img.get("url_large", img.get("url", ""))
            for img in ad.get("images", {}).get("urls_large", [])
            or [{"url": u} for u in ad.get("images", {}).get("urls", [])]
        ]

        location = ad.get("location", {})

        return CarListing(
            ad_id=ad_id,
            title=title,
            price=price,
            url=url,
            brand=attrs.get("brand", "").lower(),
            model=attrs.get("model", "").lower(),
            year=int(attrs.get("regdate", 0) or 0),
            mileage=int(attrs.get("mileage", 0) or 0),
            fuel=attrs.get("fuel_vehicle", ""),
            gearbox=attrs.get("gearbox", ""),
            doors=int(attrs.get("doors", 0) or 0),
            seller_type=ad.get("owner", {}).get("type", ""),
            location_city=location.get("city", ""),
            location_dept=location.get("department_id", ""),
            published_at=ad.get("first_publication_date", ""),
            images=images[:5],
            description=ad.get("body", ""),
        )
    except Exception as exc:
        logger.debug("Erreur parsing annonce %s : %s", ad.get("list_id"), exc)
        return None


class LeBonCoinScraper:
    """Client pour l'API de recherche LeBonCoin."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.client = httpx.Client(
            headers=HEADERS,
            timeout=config.http_timeout,
            follow_redirects=True,
        )

    def _sleep(self):
        delay = self.config.request_delay + random.uniform(0, self.config.request_jitter)
        time.sleep(delay)

    def search(self, criteria: SearchCriteria) -> list[CarListing]:
        """Lance une recherche complète (toutes les pages configurées)."""
        listings: list[CarListing] = []
        offset = 0

        for page in range(self.config.max_pages):
            page_listings, total = self._search_page(criteria, offset)
            listings.extend(page_listings)
            logger.info(
                "Page %d/%d — %d annonces récupérées (total: %d)",
                page + 1, self.config.max_pages, len(page_listings), total,
            )

            offset += self.config.ads_per_page
            if offset >= total or not page_listings:
                break

            self._sleep()

        return listings

    def _search_page(self, criteria: SearchCriteria, offset: int) -> tuple[list[CarListing], int]:
        """Récupère une page de résultats. Retourne (annonces, total_count)."""
        payload = _build_search_payload(criteria, offset, self.config.ads_per_page)

        for attempt in range(3):
            try:
                resp = self.client.post(LBC_SEARCH_URL, json=payload)
                resp.raise_for_status()
                data = resp.json()
                break
            except httpx.HTTPStatusError as exc:
                logger.warning("HTTP %d (tentative %d/3)", exc.response.status_code, attempt + 1)
                if exc.response.status_code == 429:
                    time.sleep(10 * (attempt + 1))
                elif exc.response.status_code >= 500:
                    time.sleep(5)
                else:
                    return [], 0
            except Exception as exc:
                logger.warning("Erreur réseau (tentative %d/3) : %s", attempt + 1, exc)
                time.sleep(3 * (attempt + 1))
        else:
            logger.error("Impossible de récupérer la page après 3 tentatives.")
            return [], 0

        ads_raw = data.get("ads", [])
        total = data.get("total", 0)

        listings = [l for ad in ads_raw if (l := _parse_listing(ad)) is not None]
        return listings, total

    def get_market_sample(self, brand: str, model: str, year: int) -> list[CarListing]:
        """
        Récupère un échantillon d'annonces similaires pour estimer le prix marché.
        Utilise une fenêtre de ±2 ans autour de l'année cible.
        """
        criteria = SearchCriteria(
            brands=[brand] if brand else [],
            models=[model] if model else [],
            year_min=max(year - 2, 2000),
            year_max=year + 2,
            price_min=100,
            price_max=50000,
        )
        # Un seul page suffit pour l'échantillon
        old_max = self.config.max_pages
        self.config.max_pages = 2
        sample = self.search(criteria)
        self.config.max_pages = old_max
        return sample

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
