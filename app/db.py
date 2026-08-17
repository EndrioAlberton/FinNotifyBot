"""Camada de persistencia: palavras-chave, deduplicacao e limite de alertas."""

import sqlite3
import time
from typing import List, Optional, Tuple

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS keywords (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    term       TEXT NOT NULL,
    term_norm  TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS seen (
    hash       TEXT PRIMARY KEY,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    term_norm  TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_term_time ON alerts(term_norm, created_at);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_conn: Optional[sqlite3.Connection] = None


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
        _conn.commit()
    return _conn


# ---------------------------------------------------------------- keywords

def add_keyword(term: str, term_norm: str) -> bool:
    """Retorna False se o termo ja existia."""
    try:
        conn().execute(
            "INSERT INTO keywords (term, term_norm, created_at) VALUES (?, ?, ?)",
            (term, term_norm, time.time()),
        )
        conn().commit()
        return True
    except sqlite3.IntegrityError:
        return False


def list_keywords() -> List[sqlite3.Row]:
    return conn().execute(
        "SELECT id, term, term_norm FROM keywords ORDER BY id"
    ).fetchall()


def delete_keyword(kw_id: int) -> Optional[str]:
    row = conn().execute("SELECT term FROM keywords WHERE id = ?", (kw_id,)).fetchone()
    if row is None:
        return None
    conn().execute("DELETE FROM keywords WHERE id = ?", (kw_id,))
    conn().commit()
    return row["term"]


# --------------------------------------------------------------- dedupe

def already_seen(digest: str, ttl_hours: int) -> bool:
    now = time.time()
    conn().execute("DELETE FROM seen WHERE created_at < ?", (now - ttl_hours * 3600,))
    row = conn().execute("SELECT 1 FROM seen WHERE hash = ?", (digest,)).fetchone()
    if row is not None:
        conn().commit()
        return True
    conn().execute("INSERT INTO seen (hash, created_at) VALUES (?, ?)", (digest, now))
    conn().commit()
    return False


# ----------------------------------------------------------- rate limiting

def can_alert(term_norm: str, max_per_hour: int) -> bool:
    cutoff = time.time() - 3600
    conn().execute("DELETE FROM alerts WHERE created_at < ?", (cutoff - 86400,))
    count = conn().execute(
        "SELECT COUNT(*) AS c FROM alerts WHERE term_norm = ? AND created_at > ?",
        (term_norm, cutoff),
    ).fetchone()["c"]
    conn().commit()
    return count < max_per_hour


def record_alert(term_norm: str) -> None:
    conn().execute(
        "INSERT INTO alerts (term_norm, created_at) VALUES (?, ?)",
        (term_norm, time.time()),
    )
    conn().commit()


def stats_last_24h() -> List[Tuple[str, int]]:
    cutoff = time.time() - 86400
    rows = conn().execute(
        "SELECT term_norm, COUNT(*) AS c FROM alerts WHERE created_at > ? "
        "GROUP BY term_norm ORDER BY c DESC",
        (cutoff,),
    ).fetchall()
    return [(r["term_norm"], r["c"]) for r in rows]


# ---------------------------------------------------------------- settings

def get_setting(key: str, default: str = "") -> str:
    row = conn().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    conn().execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn().commit()


def is_paused() -> bool:
    return get_setting("paused", "0") == "1"
