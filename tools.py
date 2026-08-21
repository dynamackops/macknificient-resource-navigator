"""
Shared @tool functions for the Macknificient World Resource Navigator.

Both the Family Matching Agent and the Discovery & Vetting Agent are
built from this same toolset against resources.db:

- query_resources: read-only, category/keyword search for the Matching Agent
- db_read / db_write: generic, whitelisted table access for either agent
- flag_for_review: escalation for the Discovery Agent's ambiguous/duplicate cases

All SQL here is parameterized; table/column names touched by db_read and
db_write are restricted to an explicit whitelist so an agent can never be
tricked (by prompt injection from web content, etc.) into running arbitrary
SQL against the database.
"""

import json
import sqlite3
from typing import Optional

from strands import tool

from db import get_connection, ensure_review_table, now_iso, VALID_CATEGORIES

RESOURCE_COLUMNS = [
    "id", "name", "category", "description", "eligibility", "cost",
    "service_area", "contact", "source_url", "confidence",
    "last_verified_at", "created_at",
]

# Columns an agent is allowed to write via db_write, per table.
WRITABLE_TABLES = {
    "resources": {
        "insert_required": ["name", "category", "description"],
        "insert_optional": [
            "eligibility", "cost", "service_area", "contact",
            "source_url", "confidence",
        ],
        "update_allowed": [
            "name", "category", "description", "eligibility", "cost",
            "service_area", "contact", "source_url", "confidence",
            "last_verified_at",
        ],
    },
    "review_queue": {
        "insert_required": ["reason"],
        "insert_optional": ["resource_id", "candidate_json", "status"],
        "update_allowed": ["status"],
    },
}


@tool
def query_resources(
    category: Optional[str] = None,
    keywords: Optional[str] = None,
    service_area_hint: Optional[str] = None,
    limit: int = 25,
) -> list[dict]:
    """Search vetted resources in resources.db.

    Use this to find candidate resources for a family. Filter by category
    when the need is clear (mental_health, neurodivergent,
    financial_assistance, youth_activities) and/or by free-text keywords
    matched against the resource name, description, and eligibility text.
    service_area_hint is matched loosely against the service_area field
    (e.g. "Hillsborough", "Tampa") — pass the county/city implied by the
    family's zip code, since resources are stored with a region, not a
    zip list. Leave arguments unset to browse broadly.

    Args:
        category: one of mental_health, neurodivergent,
            financial_assistance, youth_activities. Omit to search all.
        keywords: free-text search terms, e.g. "dance sports 8 year old".
        service_area_hint: a place name to loosely match against
            service_area, e.g. "Hillsborough" or "Tampa".
        limit: max rows to return (default 25).

    Returns:
        A list of resource dicts (all columns) ranked by nothing in
        particular — the caller (the agent) should rank and explain fit.
    """
    if category is not None and category not in VALID_CATEGORIES:
        return [{
            "error": f"Unknown category '{category}'. Valid categories: "
                     f"{sorted(VALID_CATEGORIES)}"
        }]

    clauses = []
    params: list = []

    if category:
        clauses.append("category = ?")
        params.append(category)

    if keywords:
        terms = [t.strip() for t in keywords.split() if t.strip()]
        for t in terms:
            like = f"%{t}%"
            clauses.append(
                "(name LIKE ? OR description LIKE ? OR eligibility LIKE ?)"
            )
            params.extend([like, like, like])

    if service_area_hint:
        clauses.append("service_area LIKE ?")
        params.append(f"%{service_area_hint}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT {', '.join(RESOURCE_COLUMNS)} FROM resources {where} LIMIT ?"
    params.append(max(1, min(limit, 100)))

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@tool
def db_read(table: str, filters: Optional[dict] = None, limit: int = 50) -> list[dict]:
    """Generic read from a whitelisted table in resources.db.

    Supports the 'resources' and 'review_queue' tables. filters is an
    optional dict of exact-match column=value pairs (AND-combined); only
    whitelisted columns are honored. Prefer query_resources for
    resource search — use this for lower-level lookups (e.g. reading
    review_queue, or fetching a resource by exact id).

    Args:
        table: 'resources' or 'review_queue'.
        filters: dict of column -> exact value to match.
        limit: max rows to return (default 50).
    """
    if table not in WRITABLE_TABLES:
        return [{"error": f"Unknown table '{table}'. Allowed: {list(WRITABLE_TABLES)}"}]

    conn = get_connection()
    try:
        ensure_review_table(conn)
        allowed_cols = set(
            WRITABLE_TABLES[table]["insert_required"]
            + WRITABLE_TABLES[table]["insert_optional"]
            + ["id"]
        )
        clauses = []
        params: list = []
        for col, val in (filters or {}).items():
            if col not in allowed_cols:
                return [{"error": f"Column '{col}' is not filterable on '{table}'"}]
            clauses.append(f"{col} = ?")
            params.append(val)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 200)))
        rows = conn.execute(
            f"SELECT * FROM {table} {where} LIMIT ?", params
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@tool
def db_write(table: str, action: str, data: dict, row_id: Optional[int] = None) -> dict:
    """Generic write to a whitelisted table in resources.db.

    action='insert': data must include the table's required fields;
    a new row is created (created_at/last_verified_at are stamped
    automatically for 'resources').
    action='update': row_id is required; only whitelisted columns in
    data are updated.

    Args:
        table: 'resources' or 'review_queue'.
        action: 'insert' or 'update'.
        data: column -> value pairs to write.
        row_id: required for action='update', the id of the row to change.
    """
    if table not in WRITABLE_TABLES:
        return {"error": f"Unknown table '{table}'. Allowed: {list(WRITABLE_TABLES)}"}
    spec = WRITABLE_TABLES[table]

    conn = get_connection()
    try:
        ensure_review_table(conn)

        if action == "insert":
            missing = [c for c in spec["insert_required"] if c not in data]
            if missing:
                return {"error": f"Missing required fields for insert: {missing}"}
            allowed = set(spec["insert_required"] + spec["insert_optional"])
            unknown = [c for c in data if c not in allowed]
            if unknown:
                return {"error": f"Unknown fields for '{table}' insert: {unknown}"}

            row = {
                c: (json.dumps(v) if table == "review_queue" and c == "candidate_json"
                    and isinstance(v, (dict, list)) else v)
                for c, v in data.items()
            }

            if table == "resources":
                stamp = now_iso()
                row.setdefault("confidence", "unverified")
                row["last_verified_at"] = stamp
                row["created_at"] = stamp
            if table == "review_queue":
                row.setdefault("status", "pending")
                row["created_at"] = now_iso()

            cols = list(row.keys())
            values = list(row.values())
            placeholders = ", ".join("?" for _ in cols)
            sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
            cur = conn.execute(sql, values)
            conn.commit()
            return {"status": "ok", "id": cur.lastrowid}

        elif action == "update":
            if row_id is None:
                return {"error": "row_id is required for action='update'"}
            allowed = set(spec["update_allowed"])
            unknown = [c for c in data if c not in allowed]
            if unknown:
                return {"error": f"Unknown/non-updatable fields for '{table}': {unknown}"}
            if not data:
                return {"error": "No fields provided to update"}
            set_clause = ", ".join(f"{c} = ?" for c in data)
            values = list(data.values()) + [row_id]
            conn.execute(
                f"UPDATE {table} SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
            return {"status": "ok", "id": row_id}

        else:
            return {"error": f"Unknown action '{action}'. Use 'insert' or 'update'."}
    finally:
        conn.close()


@tool
def mark_verified(resource_id: int) -> dict:
    """Stamp an existing resource as freshly re-verified.

    Use this after fetch_url confirms a resource's source_url still
    resolves and its content still matches what's stored (no closure/
    discontinuation language, eligibility unchanged) — the mechanically
    verifiable, no-judgment-needed case. Sets last_verified_at to now.
    For anything stale, dead, or ambiguous, use flag_for_review instead.

    Args:
        resource_id: id of the resource in the resources table.
    """
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE resources SET last_verified_at = ? WHERE id = ?",
            (now_iso(), resource_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return {"error": f"No resource with id {resource_id}"}
        return {"status": "verified", "id": resource_id}
    finally:
        conn.close()


@tool
def flag_for_review(reason: str, resource_id: Optional[int] = None, candidate: Optional[dict] = None) -> dict:
    """Escalate an ambiguous or duplicate resource to a human reviewer.

    Use this instead of silently approving or rejecting when a
    resource's eligibility is ambiguous, it looks like a duplicate of an
    existing entry, or a mechanically-unverifiable judgment call is
    needed. Do NOT use this for clear-cut cases (dead link, obviously
    new/unique resource) — handle those directly via db_write.

    Args:
        reason: why this needs human judgment, e.g. "possible duplicate
            of resource id 12" or "eligibility criteria unclear from
            source page".
        resource_id: id of the existing resource in question, if any.
        candidate: proposed new/updated field values, if any, e.g. a
            newly-discovered resource's structured data.
    """
    conn = get_connection()
    try:
        ensure_review_table(conn)
        cur = conn.execute(
            """INSERT INTO review_queue
               (resource_id, candidate_json, reason, status, created_at)
               VALUES (?, ?, ?, 'pending', ?)""",
            (
                resource_id,
                json.dumps(candidate) if candidate else None,
                reason,
                now_iso(),
            ),
        )
        conn.commit()
        return {"status": "flagged", "review_id": cur.lastrowid}
    finally:
        conn.close()
