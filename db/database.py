"""
SQLite layer — schema creation, weight CRUD, regex rules, and history logging.
"""

import sqlite3
import re
from contextlib import contextmanager
from datetime import datetime
from typing import Generator

from config import DB_PATH, REGEX_RULE_THRESHOLD


# ── Connection helper ─────────────────────────────────────────────────────────

@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema ────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS weights (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    attribute   TEXT    NOT NULL,   -- 'codec', 'resolution', 'group_name', 'source'
    value       TEXT    NOT NULL,
    score       REAL    NOT NULL DEFAULT 0,
    pick_count  INTEGER NOT NULL DEFAULT 0,
    UNIQUE(attribute, value)
);

CREATE TABLE IF NOT EXISTS regex_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern     TEXT    NOT NULL UNIQUE,
    bonus       REAL    NOT NULL DEFAULT 50,
    created_at  TEXT    NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    query           TEXT    NOT NULL,
    torrent_title   TEXT    NOT NULL,
    group_name      TEXT,
    codec           TEXT,
    resolution      TEXT,
    source          TEXT,
    size_bytes      INTEGER,
    info_url        TEXT,
    chosen_at       TEXT    NOT NULL
);
"""


def init_db() -> None:
    """Create tables if they don't exist yet."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ── Weight helpers ────────────────────────────────────────────────────────────

def get_all_weights() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM weights ORDER BY score DESC").fetchall()
    return [dict(r) for r in rows]


def get_weight(attribute: str, value: str) -> float:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT score FROM weights WHERE attribute=? AND value=?",
            (attribute, value),
        ).fetchone()
    return row["score"] if row else 0.0


def upsert_weight(attribute: str, value: str, delta: float = 10.0) -> None:
    """Increment the score for an attribute/value pair and bump pick_count."""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO weights (attribute, value, score, pick_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(attribute, value) DO UPDATE SET
                score      = score + excluded.score,
                pick_count = pick_count + 1
            """,
            (attribute, value, delta),
        )
        # Check if we should auto-generate a regex rule
        row = conn.execute(
            "SELECT pick_count FROM weights WHERE attribute=? AND value=?",
            (attribute, value),
        ).fetchone()
        if row and row["pick_count"] >= REGEX_RULE_THRESHOLD and attribute == "group_name":
            _maybe_create_regex_rule(conn, value)


def _maybe_create_regex_rule(conn: sqlite3.Connection, group_name: str) -> None:
    """Auto-generate a regex rule for a consistently chosen release group."""
    # Escape the group name for safe regex use
    escaped = re.escape(group_name)
    pattern = rf"(?i)\b{escaped}\b"
    exists = conn.execute(
        "SELECT id FROM regex_rules WHERE pattern=?", (pattern,)
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO regex_rules (pattern, bonus, created_at) VALUES (?, ?, ?)",
            (pattern, 50.0, datetime.utcnow().isoformat()),
        )


# ── Regex rule helpers ────────────────────────────────────────────────────────

def get_active_regex_rules() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM regex_rules WHERE active=1"
        ).fetchall()
    return [dict(r) for r in rows]


# ── History helpers ───────────────────────────────────────────────────────────

def log_selection(
    query: str,
    torrent_title: str,
    group_name: str | None,
    codec: str | None,
    resolution: str | None,
    source: str | None,
    size_bytes: int | None,
    info_url: str | None = None,
) -> None:
    with get_conn() as conn:
        # Add info_url column if it doesn't exist yet (migration for existing DBs)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(history)").fetchall()]
        if "info_url" not in cols:
            conn.execute("ALTER TABLE history ADD COLUMN info_url TEXT")
        conn.execute(
            """
            INSERT INTO history
                (query, torrent_title, group_name, codec, resolution, source, size_bytes, info_url, chosen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query, torrent_title, group_name, codec,
                resolution, source, size_bytes, info_url,
                datetime.utcnow().isoformat(),
            ),
        )


def get_history(limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM history ORDER BY chosen_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Delete helpers ────────────────────────────────────────────────────────────

def delete_history_entry(entry_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM history WHERE id=?", (entry_id,))

def clear_all_history() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM history")

def delete_weight(weight_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM weights WHERE id=?", (weight_id,))

def clear_all_weights() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM weights")

def delete_regex_rule(rule_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM regex_rules WHERE id=?", (rule_id,))

def clear_all_regex_rules() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM regex_rules")


# ── Search query history ──────────────────────────────────────────────────────

SEARCH_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_queries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    query      TEXT    NOT NULL,
    prompt     TEXT    NOT NULL,
    searched_at TEXT   NOT NULL
);
"""

def init_search_history() -> None:
    with get_conn() as conn:
        conn.executescript(SEARCH_HISTORY_SCHEMA)

def log_search_query(prompt: str, query: str) -> None:
    """Save a search prompt (deduplicates consecutive identical prompts)."""
    with get_conn() as conn:
        last = conn.execute(
            "SELECT prompt FROM search_queries ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if last and last["prompt"] == prompt:
            return  # don't log duplicates back-to-back
        conn.execute(
            "INSERT INTO search_queries (query, prompt, searched_at) VALUES (?, ?, ?)",
            (query, prompt, datetime.utcnow().isoformat()),
        )

def get_search_queries(limit: int = 30) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM search_queries ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]

def delete_search_query(entry_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM search_queries WHERE id=?", (entry_id,))

def clear_all_search_queries() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM search_queries")
