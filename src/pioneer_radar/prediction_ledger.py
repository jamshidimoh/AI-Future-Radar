"""SQLite-backed claim/prediction ledger with outcome tracking.

The runtime database is intentionally not committed. This module creates it on demand.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims_and_falsifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person TEXT NOT NULL,
    claim TEXT NOT NULL,
    topic TEXT NOT NULL,
    claim_date TEXT,
    source_url TEXT,
    evidence TEXT,
    horizon TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    evaluated_date TEXT,
    outcome TEXT,
    confidence REAL,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_claim_person_topic ON claims_and_falsifications(person, topic);
CREATE INDEX IF NOT EXISTS idx_claim_status ON claims_and_falsifications(status);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def add_claim(conn: sqlite3.Connection, *, person: str, claim: str, topic: str,
              claim_date: str | None = None, source_url: str | None = None,
              evidence: str | None = None, horizon: str | None = None,
              confidence: float | None = None, notes: str | None = None) -> int:
    cur = conn.execute(
        """INSERT INTO claims_and_falsifications
        (person, claim, topic, claim_date, source_url, evidence, horizon, confidence, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (person, claim, topic, claim_date, source_url, evidence, horizon, confidence, notes),
    )
    conn.commit()
    return int(cur.lastrowid)


def recent_claims(conn: sqlite3.Connection, person: str, topic: str, limit: int = 5) -> list[dict]:
    rows = conn.execute(
        """SELECT id, person, claim, topic, claim_date, source_url, status, evaluated_date, outcome, confidence, notes
        FROM claims_and_falsifications
        WHERE person = ? AND topic = ?
        ORDER BY COALESCE(claim_date, '') DESC, id DESC LIMIT ?""",
        (person, topic, int(limit)),
    ).fetchall()
    names = ["id", "person", "claim", "topic", "claim_date", "source_url", "status", "evaluated_date", "outcome", "confidence", "notes"]
    return [dict(zip(names, row)) for row in rows]


def record_outcome(conn: sqlite3.Connection, claim_id: int, *, status: str,
                    evaluated_date: str | None, outcome: str | None,
                    notes: str | None = None) -> None:
    conn.execute(
        """UPDATE claims_and_falsifications
        SET status=?, evaluated_date=?, outcome=?, notes=COALESCE(?, notes)
        WHERE id=?""",
        (status, evaluated_date, outcome, notes, int(claim_id)),
    )
    conn.commit()
