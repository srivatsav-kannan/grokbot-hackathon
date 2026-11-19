"""SQLite file location and table creation."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "fairlot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    price INTEGER NOT NULL,
    photos TEXT NOT NULL,
    neighborhood TEXT NOT NULL,
    source_url TEXT,
    posted_at TEXT NOT NULL,
    origin TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS appraisals (
    listing_id TEXT PRIMARY KEY,
    estimated_value INTEGER NOT NULL,
    low INTEGER NOT NULL,
    high INTEGER NOT NULL,
    comps TEXT NOT NULL,
    verdict TEXT NOT NULL,
    FOREIGN KEY (listing_id) REFERENCES listings(id)
);

CREATE TABLE IF NOT EXISTS inspections (
    listing_id TEXT PRIMARY KEY,
    trust_level TEXT NOT NULL,
    signals TEXT NOT NULL,
    FOREIGN KEY (listing_id) REFERENCES listings(id)
);

CREATE TABLE IF NOT EXISTS negotiations (
    id TEXT PRIMARY KEY,
    listing_id TEXT NOT NULL,
    want_id TEXT,
    status TEXT NOT NULL,
    outcome TEXT NOT NULL,
    messages TEXT NOT NULL,
    FOREIGN KEY (listing_id) REFERENCES listings(id)
);

CREATE TABLE IF NOT EXISTS price_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id TEXT,
    want_id TEXT,
    buyer_max INTEGER,
    seller_min INTEGER
);

CREATE TABLE IF NOT EXISTS wants (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    category TEXT,
    area TEXT,
    keywords TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS want_access (
    want_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL,
    FOREIGN KEY (want_id) REFERENCES wants(id)
);

CREATE TABLE IF NOT EXISTS want_matches (
    want_id TEXT NOT NULL,
    listing_id TEXT NOT NULL,
    score REAL NOT NULL,
    reason TEXT NOT NULL,
    negotiation_id TEXT,
    PRIMARY KEY (want_id, listing_id),
    FOREIGN KEY (want_id) REFERENCES wants(id),
    FOREIGN KEY (listing_id) REFERENCES listings(id)
);
"""


def db_path() -> Path:
    override = os.environ.get("DATABASE_PATH", "").strip()
    if override:
        return Path(override)
    return DEFAULT_PATH


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) AS n FROM listings").fetchone()["n"]
    if count == 0:
        from backend.app.seed import load_seed

        load_seed()
