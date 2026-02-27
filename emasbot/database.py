from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    """Initialize SQLite schema."""
    with _connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS last_price (
                weight_grams INTEGER PRIMARY KEY,
                sell_price INTEGER NOT NULL,
                buyback_price INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        # New schema (vendor + weight), supports fractional weights (e.g. 0.5g).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS last_vendor_price (
                vendor_id TEXT NOT NULL,
                weight_text TEXT NOT NULL,
                weight_grams REAL,
                sell_price INTEGER NOT NULL,
                buyback_price INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (vendor_id, weight_text)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vendor_price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_id TEXT NOT NULL,
                weight_text TEXT NOT NULL,
                weight_grams REAL,
                sell_price INTEGER NOT NULL,
                buyback_price INTEGER NOT NULL,
                observed_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_vendor_history_vendor_weight_time
            ON vendor_price_history(vendor_id, weight_text, observed_at);
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weight_grams INTEGER NOT NULL,
                sell_price INTEGER NOT NULL,
                buyback_price INTEGER NOT NULL,
                observed_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_price_history_weight_time ON price_history(weight_grams, observed_at);"
        )

    logger.info("DB initialized: %s", db_path)


def get_last_price(db_path: str, weight_grams: int = 25) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "SELECT weight_grams, sell_price, buyback_price, updated_at FROM last_price WHERE weight_grams = ?",
            (weight_grams,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return dict(row)


def upsert_last_price(
    db_path: str,
    weight_grams: int,
    sell_price: int,
    buyback_price: int,
    updated_at: datetime,
) -> None:
    updated_at_text = updated_at.isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO last_price(weight_grams, sell_price, buyback_price, updated_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(weight_grams) DO UPDATE SET
              sell_price=excluded.sell_price,
              buyback_price=excluded.buyback_price,
              updated_at=excluded.updated_at;
            """,
            (weight_grams, sell_price, buyback_price, updated_at_text),
        )
    logger.info(
        "Upsert last_price weight=%s sell=%s buyback=%s at=%s",
        weight_grams,
        sell_price,
        buyback_price,
        updated_at_text,
    )


def insert_history(
    db_path: str,
    weight_grams: int,
    sell_price: int,
    buyback_price: int,
    observed_at: datetime,
) -> None:
    observed_at_text = observed_at.isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO price_history(weight_grams, sell_price, buyback_price, observed_at)
            VALUES(?, ?, ?, ?)
            """,
            (weight_grams, sell_price, buyback_price, observed_at_text),
        )
    logger.info(
        "Inserted history weight=%s sell=%s buyback=%s at=%s",
        weight_grams,
        sell_price,
        buyback_price,
        observed_at_text,
    )


def get_last_vendor_price(
    db_path: str, vendor_id: str, weight_text: str
) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            SELECT vendor_id, weight_text, weight_grams, sell_price, buyback_price, updated_at
            FROM last_vendor_price
            WHERE vendor_id = ? AND weight_text = ?
            """,
            (vendor_id, weight_text),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return dict(row)


def upsert_last_vendor_price(
    db_path: str,
    vendor_id: str,
    weight_text: str,
    weight_grams: float | None,
    sell_price: int,
    buyback_price: int,
    updated_at: datetime,
) -> None:
    updated_at_text = updated_at.isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO last_vendor_price(
                vendor_id, weight_text, weight_grams, sell_price, buyback_price, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(vendor_id, weight_text) DO UPDATE SET
              weight_grams=excluded.weight_grams,
              sell_price=excluded.sell_price,
              buyback_price=excluded.buyback_price,
              updated_at=excluded.updated_at;
            """,
            (
                vendor_id,
                weight_text,
                weight_grams,
                sell_price,
                buyback_price,
                updated_at_text,
            ),
        )
    logger.info(
        "Upsert last_vendor_price vendor=%s weight=%s sell=%s buyback=%s at=%s",
        vendor_id,
        weight_text,
        sell_price,
        buyback_price,
        updated_at_text,
    )


def insert_vendor_history(
    db_path: str,
    vendor_id: str,
    weight_text: str,
    weight_grams: float | None,
    sell_price: int,
    buyback_price: int,
    observed_at: datetime,
) -> None:
    observed_at_text = observed_at.isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO vendor_price_history(
                vendor_id, weight_text, weight_grams, sell_price, buyback_price, observed_at
            )
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                vendor_id,
                weight_text,
                weight_grams,
                sell_price,
                buyback_price,
                observed_at_text,
            ),
        )
    logger.info(
        "Inserted vendor history vendor=%s weight=%s sell=%s buyback=%s at=%s",
        vendor_id,
        weight_text,
        sell_price,
        buyback_price,
        observed_at_text,
    )
