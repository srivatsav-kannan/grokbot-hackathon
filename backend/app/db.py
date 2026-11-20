"""SQLite by default. Postgres when DATABASE_URL is set.

Render's disk is wiped on deploy and on free-tier spin-down, so /tmp/fairlot.db
cannot hold accounts. Set DATABASE_URL to the shared Postgres URL
(postgres:// or postgresql://). Fairlot creates and uses only the schema
named fairlot. It never creates or alters anything in public.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection as SAConnection
from sqlalchemy.engine import Engine

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
    origin TEXT NOT NULL,
    user_id TEXT,
    status TEXT NOT NULL DEFAULT 'active'
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
    accepted INTEGER NOT NULL DEFAULT 0,
    user_id TEXT,
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
    created_at TEXT NOT NULL,
    user_id TEXT
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

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    href TEXT,
    read_at TEXT
);

CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    listing_id TEXT NOT NULL,
    buyer_id TEXT NOT NULL,
    want_id TEXT,
    buyer_mode TEXT NOT NULL,
    seller_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (listing_id, buyer_id)
);

CREATE TABLE IF NOT EXISTS thread_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    at TEXT NOT NULL,
    author TEXT NOT NULL,
    kind TEXT NOT NULL,
    amount INTEGER,
    body TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS thread_limits (
    thread_id TEXT PRIMARY KEY,
    buyer_ceiling INTEGER,
    seller_floor INTEGER
);

CREATE TABLE IF NOT EXISTS completions (
    id TEXT PRIMARY KEY,
    listing_id TEXT NOT NULL UNIQUE,
    buyer_id TEXT NOT NULL,
    seller_id TEXT,
    thread_id TEXT,
    price INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    user_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    key TEXT NOT NULL,
    record_id TEXT NOT NULL,
    PRIMARY KEY (user_id, scope, key)
);

CREATE TABLE IF NOT EXISTS recommendations (
    want_id TEXT NOT NULL,
    listing_id TEXT NOT NULL,
    suggested_offer INTEGER NOT NULL,
    message TEXT NOT NULL,
    PRIMARY KEY (want_id, listing_id),
    FOREIGN KEY (want_id) REFERENCES wants(id),
    FOREIGN KEY (listing_id) REFERENCES listings(id)
);
"""


_SCHEMA_NAME = "fairlot"
_engines: dict[str, tuple[Engine, str]] = {}


def db_path() -> Path:
    override = os.environ.get("DATABASE_PATH", "").strip()
    if override:
        return Path(override)
    return DEFAULT_PATH


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "").strip()


def using_postgres() -> bool:
    return bool(database_url())


def _sqlalchemy_url() -> tuple[str, str]:
    raw = database_url()
    if not raw:
        path = db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+pysqlite:///{path}", "sqlite"
    if raw.startswith("postgres://"):
        raw = "postgresql+psycopg://" + raw[len("postgres://") :]
    elif raw.startswith("postgresql://"):
        raw = "postgresql+psycopg://" + raw[len("postgresql://") :]
    return raw, "postgresql"


def _engine() -> tuple[Engine, str]:
    url, dialect = _sqlalchemy_url()
    cached = _engines.get(url)
    if cached is not None:
        return cached
    kwargs: dict = {"pool_pre_ping": True}
    if dialect == "sqlite":
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # Every connection, including pooled ones, stays inside schema fairlot.
        kwargs["connect_args"] = {"options": f"-csearch_path={_SCHEMA_NAME}"}
    engine = create_engine(url, **kwargs)
    if dialect == "sqlite":

        @event.listens_for(engine, "connect")
        def _sqlite_fk(dbapi_connection, _record) -> None:
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    else:

        @event.listens_for(engine, "connect")
        def _fairlot_path(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute(f"SET search_path TO {_SCHEMA_NAME}")
            cursor.close()

    _engines[url] = (engine, dialect)
    return engine, dialect


class _Result:
    def __init__(self, rows: list, rowcount: int = 0) -> None:
        self._rows = rows
        self.rowcount = rowcount

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


def _bind(sql: str, params) -> tuple[str, dict]:
    if isinstance(params, dict):
        return sql, params
    if params is None:
        params = ()
    if not isinstance(params, (list, tuple)):
        params = (params,)
    binds: dict[str, object] = {}
    out: list[str] = []
    index = 0
    quoted = False
    for char in sql:
        if char == "'":
            quoted = not quoted
            out.append(char)
        elif char == "?" and not quoted:
            key = f"p{index}"
            out.append(f":{key}")
            binds[key] = params[index]
            index += 1
        else:
            out.append(char)
    return "".join(out), binds


def _split_sql(script: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    quoted = False
    for char in script:
        if char == "'":
            quoted = not quoted
        if char == ";" and not quoted:
            statement = "".join(buf).strip()
            if statement:
                parts.append(statement)
            buf = []
        else:
            buf.append(char)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


class Connection:
    """Small wrapper so existing `?` queries work on SQLite and Postgres."""

    def __init__(self, raw: SAConnection, dialect: str) -> None:
        self._raw = raw
        self.dialect = dialect

    def execute(self, sql: str, params=()) -> _Result:
        statement = sql.strip()
        if statement.upper().startswith("PRAGMA TABLE_INFO"):
            return self._table_info(statement)
        if statement.upper().startswith("PRAGMA"):
            if self.dialect != "sqlite":
                return _Result([])
        return self._exec(sql, params)

    def executescript(self, script: str) -> None:
        body = script
        if self.dialect == "postgresql":
            body = body.replace(
                "INTEGER PRIMARY KEY AUTOINCREMENT",
                "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY",
            )
        for statement in _split_sql(body):
            self.execute(statement)

    def _table_info(self, statement: str) -> _Result:
        match = re.search(r"table_info\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)", statement, re.I)
        if match is None:
            return _Result([])
        table = match.group(1)
        if self.dialect == "postgresql":
            return self._exec(
                """
                SELECT column_name AS name
                FROM information_schema.columns
                WHERE table_schema = 'fairlot' AND table_name = :table
                """,
                {"table": table},
            )
        return self._exec(f"PRAGMA table_info({table})")

    def _exec(self, sql: str, params=()) -> _Result:
        converted, binds = _bind(sql, params)
        result = self._raw.execute(text(converted), binds)
        if result.returns_rows:
            return _Result(list(result.mappings().all()), result.rowcount or 0)
        return _Result([], result.rowcount or 0)

    def __enter__(self) -> "Connection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                self._raw.commit()
            else:
                self._raw.rollback()
        finally:
            self._raw.close()


def connect() -> Connection:
    engine, dialect = _engine()
    return Connection(engine.connect(), dialect)


def _ensure_fairlot_schema() -> None:
    """Create the fairlot schema only. Does not read or write public tables."""

    engine, _dialect = _engine()
    with engine.connect() as raw:
        raw.execute(text("CREATE SCHEMA IF NOT EXISTS fairlot"))
        raw.execute(text("SET search_path TO fairlot"))
        raw.commit()


def _column_names(conn: Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_column(conn: Connection, table: str, name: str, ddl: str) -> None:
    if name not in _column_names(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db() -> None:
    if using_postgres():
        _ensure_fairlot_schema()
    with connect() as conn:
        conn.executescript(SCHEMA)
        _add_column(conn, "listings", "user_id", "TEXT")
        _add_column(conn, "listings", "status", "TEXT NOT NULL DEFAULT 'active'")
        _add_column(conn, "wants", "user_id", "TEXT")
        _add_column(conn, "negotiations", "user_id", "TEXT")
        _add_column(conn, "negotiations", "accepted", "INTEGER NOT NULL DEFAULT 0")
        count = conn.execute("SELECT COUNT(*) AS n FROM listings").fetchone()["n"]
    if count == 0:
        from backend.app.seed import load_seed

        load_seed()
