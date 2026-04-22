"""
Base de données SQLite — stockage des annonces et des résultats d'analyse.
"""
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from .analyzer import DealResult
from .scraper import CarListing

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    ad_id           TEXT PRIMARY KEY,
    title           TEXT,
    price           INTEGER,
    url             TEXT,
    brand           TEXT,
    model           TEXT,
    year            INTEGER,
    mileage         INTEGER,
    fuel            TEXT,
    gearbox         TEXT,
    doors           INTEGER,
    seller_type     TEXT,
    location_city   TEXT,
    location_dept   TEXT,
    published_at    TEXT,
    images          TEXT,       -- JSON array
    description     TEXT,
    first_seen_at   TEXT,
    last_seen_at    TEXT
);

CREATE TABLE IF NOT EXISTS deal_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ad_id           TEXT NOT NULL,
    market_price    REAL,
    price_gap_pct   REAL,
    estimated_resale REAL,
    estimated_profit REAL,
    deal_score      INTEGER,
    sample_size     INTEGER,
    is_deal         INTEGER,    -- 0/1
    reasons         TEXT,       -- JSON array
    analyzed_at     TEXT,
    FOREIGN KEY(ad_id) REFERENCES listings(ad_id)
);

CREATE INDEX IF NOT EXISTS idx_deal_score ON deal_results(deal_score DESC);
CREATE INDEX IF NOT EXISTS idx_listings_brand ON listings(brand, model);
"""


class Database:
    """Accès à la base SQLite des annonces."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    # ── Listings ─────────────────────────────────────────────────────────────

    def upsert_listing(self, listing: CarListing) -> bool:
        """Insère ou met à jour une annonce. Retourne True si nouvelle."""
        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT ad_id FROM listings WHERE ad_id = ?", (listing.ad_id,)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE listings SET last_seen_at=?, price=? WHERE ad_id=?",
                    (now, listing.price, listing.ad_id),
                )
                return False

            conn.execute(
                """INSERT INTO listings
                (ad_id, title, price, url, brand, model, year, mileage, fuel,
                 gearbox, doors, seller_type, location_city, location_dept,
                 published_at, images, description, first_seen_at, last_seen_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    listing.ad_id, listing.title, listing.price, listing.url,
                    listing.brand, listing.model, listing.year, listing.mileage,
                    listing.fuel, listing.gearbox, listing.doors,
                    listing.seller_type, listing.location_city,
                    listing.location_dept, listing.published_at,
                    json.dumps(listing.images), listing.description, now, now,
                ),
            )
            return True

    def is_new(self, ad_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT ad_id FROM listings WHERE ad_id=?", (ad_id,)
            ).fetchone()
            return row is None

    def get_listing(self, ad_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM listings WHERE ad_id=?", (ad_id,)
            ).fetchone()
            return dict(row) if row else None

    # ── Deal results ──────────────────────────────────────────────────────────

    def save_deal_result(self, result: DealResult):
        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO deal_results
                (ad_id, market_price, price_gap_pct, estimated_resale,
                 estimated_profit, deal_score, sample_size, is_deal, reasons, analyzed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    result.listing.ad_id,
                    result.market_price,
                    result.price_gap_pct,
                    result.estimated_resale,
                    result.estimated_profit,
                    result.deal_score,
                    result.sample_size,
                    int(result.is_deal),
                    json.dumps(result.reasons),
                    now,
                ),
            )

    def get_best_deals(self, limit: int = 20) -> list[dict]:
        """Retourne les meilleures affaires détectées (les plus récentes d'abord)."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT dr.*, l.title, l.url, l.brand, l.model, l.year,
                          l.mileage, l.location_city
                   FROM deal_results dr
                   JOIN listings l ON dr.ad_id = l.ad_id
                   WHERE dr.is_deal = 1
                   ORDER BY dr.deal_score DESC, dr.analyzed_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
            deals = conn.execute(
                "SELECT COUNT(*) FROM deal_results WHERE is_deal=1"
            ).fetchone()[0]
            avg_score = conn.execute(
                "SELECT AVG(deal_score) FROM deal_results WHERE is_deal=1"
            ).fetchone()[0]
            return {
                "total_listings": total,
                "total_deals": deals,
                "avg_deal_score": round(avg_score or 0, 1),
            }
