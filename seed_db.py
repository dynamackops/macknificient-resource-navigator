"""
Seeds resources.db (SQLite) from seed_resources.json.
Run this once after Claude Code scaffolds the project's database schema,
or standalone to get a working local database immediately:

    python3 seed_db.py

Creates resources.db in the current directory if it doesn't exist yet.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "resources.db"
SEED_PATH = Path(__file__).parent / "seed_resources.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    eligibility TEXT,
    cost TEXT,
    service_area TEXT,
    contact TEXT,
    source_url TEXT,
    confidence TEXT DEFAULT 'unverified',
    last_verified_at TEXT,
    created_at TEXT NOT NULL
);
"""


def main():
    with open(SEED_PATH) as f:
        resources = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for r in resources:
        conn.execute(
            """INSERT INTO resources
               (name, category, description, eligibility, cost,
                service_area, contact, source_url, confidence,
                last_verified_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                r["name"], r["category"], r["description"], r["eligibility"],
                r["cost"], r["service_area"], r["contact"], r["source_url"],
                r["confidence"], now, now,
            ),
        )
        inserted += 1

    conn.commit()
    conn.close()
    print(f"Seeded {inserted} resources into {DB_PATH}")


if __name__ == "__main__":
    main()
