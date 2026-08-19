"""SQLite persistence layer (single-file, idempotent schema)."""
from __future__ import annotations
import os
import sqlite3
from typing import Any, Dict, List

from core import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    published_at TEXT,
    collected_at TEXT NOT NULL,
    source_category TEXT NOT NULL,
    data_authenticity TEXT NOT NULL,
    normalized_title TEXT,
    category TEXT DEFAULT 'general',
    heat_score REAL DEFAULT 0,
    recency_score REAL DEFAULT 0,
    category_score REAL DEFAULT 0,
    feedback_score REAL DEFAULT 0,
    priority_score REAL DEFAULT 0,
    priority_reasons TEXT,
    dedup_key TEXT,
    merged_from TEXT,
    follow_decision TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_key TEXT UNIQUE,
    source TEXT,
    pipeline TEXT,
    category TEXT,
    priority_score REAL,
    risk_level TEXT,
    status TEXT DEFAULT 'Draft',
    data_authenticity TEXT,
    content_json TEXT,
    reject_reason TEXT,
    revision_note TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS review_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER,
    action TEXT NOT NULL,
    reason TEXT,
    note TEXT,
    reviewed_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER,
    title TEXT,
    status TEXT DEFAULT 'draft',
    structure_template TEXT,
    performance_json TEXT,
    data_authenticity TEXT,
    published_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS assets_deleted (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER,
    title TEXT,
    status TEXT DEFAULT 'deleted',
    structure_template TEXT,
    performance_json TEXT,
    data_authenticity TEXT,
    published_at TEXT,
    deleted_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    is_primary INTEGER DEFAULT 0,
    data_authenticity TEXT
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    post_id TEXT,
    source_url TEXT,
    snippet TEXT,
    derived_features TEXT,
    public_metrics TEXT,
    content_type TEXT,
    posted_at TEXT,
    data_authenticity TEXT
);

CREATE TABLE IF NOT EXISTS feedback_weights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dimension TEXT UNIQUE,
    weight REAL NOT NULL,
    last_action TEXT,
    last_reason TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ai_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_hash TEXT UNIQUE,
    output_json TEXT,
    generation_mode TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Online-learning feedback samples: human approve/reject = supervision signal.
CREATE TABLE IF NOT EXISTS feedback_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER,
    features_json TEXT NOT NULL,
    label INTEGER NOT NULL,          -- 1 = approve, 0 = reject
    category TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


def get_conn(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or config.DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | None = None) -> None:
    conn = get_conn(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def upsert_event(conn: sqlite3.Connection, ev: "dict[str, Any]") -> int:
    """Insert or update event by dedup_key; returns row id."""
    dedup_key = ev.get("dedup_key") or ""
    if dedup_key:
        row = conn.execute(
            "SELECT id FROM events WHERE dedup_key = ?", (dedup_key,)
        ).fetchone()
        if row:
            return int(row["id"])
    cur = conn.execute(
        """
        INSERT INTO events (
            title, source, url, published_at, collected_at, source_category,
            data_authenticity, normalized_title, category, heat_score, recency_score,
            category_score, feedback_score, priority_score, priority_reasons,
            dedup_key, merged_from, follow_decision
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            ev.get("title", ""),
            ev.get("source", ""),
            ev.get("url", ""),
            ev.get("published_at", ""),
            ev.get("collected_at", ""),
            ev.get("source_category", ""),
            ev.get("data_authenticity", ""),
            ev.get("normalized_title", ""),
            ev.get("category", "general"),
            ev.get("heat_score", 0.0),
            ev.get("recency_score", 0.0),
            ev.get("category_score", 0.0),
            ev.get("feedback_score", 0.0),
            ev.get("priority_score", 0.0),
            _json(ev.get("priority_reasons", {})),
            dedup_key,
            _json(ev.get("merged_from", [])),
            ev.get("follow_decision", ""),
        ),
    )
    return int(cur.lastrowid)


def _json(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)
