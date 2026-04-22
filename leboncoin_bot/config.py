"""
Configuration du bot LeBonCoin - critères de recherche et paramètres.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchCriteria:
    """Critères pour une recherche de voitures."""
    brands: list[str] = field(default_factory=list)   # ex: ["peugeot", "renault"]
    models: list[str] = field(default_factory=list)   # ex: ["208", "clio"]
    price_min: int = 500
    price_max: int = 15000
    year_min: int = 2010
    year_max: int = 2023
    mileage_max: int = 200000
    # Régions LeBonCoin (ex: "île-de-france", "provence-alpes-côte-d'azur")
    regions: list[str] = field(default_factory=list)
    # Départements (ex: ["75", "92", "93", "94"])
    departments: list[str] = field(default_factory=list)
    fuel_types: list[str] = field(default_factory=list)  # ["essence", "diesel", "hybride", "electrique"]
    gearbox: str = ""          # "manuelle" ou "automatique"
    doors: list[int] = field(default_factory=list)     # [3, 5]


@dataclass
class AnalysisConfig:
    """Paramètres de l'analyse de prix."""
    # Pourcentage en-dessous du prix marché pour être considéré "bonne affaire"
    deal_threshold_pct: float = 20.0
    # Nombre minimum d'annonces similaires pour calculer un prix marché fiable
    min_sample_size: int = 5
    # Marge bénéficiaire cible pour la revente (%)
    target_margin_pct: float = 15.0
    # Score minimum (0-100) pour déclencher une alerte
    min_alert_score: int = 60
    # Pondération des critères de score
    weight_price_gap: float = 0.50     # Écart au prix marché
    weight_mileage: float = 0.20       # Kilométrage
    weight_age: float = 0.15           # Âge du véhicule
    weight_seller: float = 0.15        # Type de vendeur (particulier = mieux)


@dataclass
class BotConfig:
    """Configuration générale du bot."""
    # Délai entre requêtes (secondes) pour ne pas surcharger LeBonCoin
    request_delay: float = 2.0
    # Jitter aléatoire ajouté au délai (secondes)
    request_jitter: float = 1.5
    # Intervalle de scan (secondes)
    scan_interval: int = 300          # 5 minutes par défaut
    # Nombre max de pages par recherche
    max_pages: int = 5
    # Annonces par page
    ads_per_page: int = 35
    # Timeout requête HTTP (secondes)
    http_timeout: int = 15
    # Chemin vers la base SQLite
    db_path: str = "leboncoin_cars.db"
    # Activer les notifications Telegram
    telegram_enabled: bool = False
    telegram_token: str = ""
    telegram_chat_id: str = ""
    # Enregistrer les logs dans un fichier
    log_file: str = "leboncoin_bot.log"


# ─── Profils de recherche préconfigurés ───────────────────────────────────────

PROFIL_CITADINES = SearchCriteria(
    brands=["peugeot", "renault", "citroen", "volkswagen", "opel", "ford"],
    models=["208", "clio", "c3", "polo", "corsa", "fiesta"],
    price_min=2000,
    price_max=10000,
    year_min=2012,
    mileage_max=180000,
    fuel_types=["essence", "diesel"],
)

PROFIL_COMPACTES = SearchCriteria(
    brands=["peugeot", "renault", "volkswagen", "bmw", "audi", "mercedes"],
    models=["308", "megane", "golf", "serie-1", "a3", "classe-a"],
    price_min=4000,
    price_max=15000,
    year_min=2013,
    mileage_max=160000,
)

PROFIL_SUV_ABORDABLES = SearchCriteria(
    brands=["dacia", "peugeot", "renault", "opel", "ford", "seat"],
    models=["duster", "2008", "kadjar", "mokka", "ecosport", "ateca"],
    price_min=5000,
    price_max=15000,
    year_min=2014,
    mileage_max=150000,
)

PROFIL_PREMIUM = SearchCriteria(
    brands=["bmw", "audi", "mercedes", "lexus", "volvo"],
    price_min=8000,
    price_max=25000,
    year_min=2015,
    mileage_max=130000,
)

# Profil actif par défaut
DEFAULT_SEARCH = PROFIL_CITADINES
DEFAULT_ANALYSIS = AnalysisConfig()
DEFAULT_BOT = BotConfig()
