"""
Shared SQLite access for resources.db.

Both agents (Family Matching and Discovery & Vetting) go through this
module rather than opening their own connections, so the schema and
connection settings live in exactly one place.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "resources.db"

VALID_CATEGORIES = {
    "mental_health",
    "neurodivergent",
    "financial_assistance",
    "youth_activities",
}


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_review_table(conn: sqlite3.Connection) -> None:
    """Escalation queue for the Discovery Agent's flag_for_review tool."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS review_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id INTEGER,
            candidate_json TEXT,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )"""
    )
    conn.commit()
