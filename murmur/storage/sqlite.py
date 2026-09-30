# murmur/storage/sqlite.py
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".murmur" / "findings.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    repo TEXT NOT NULL,
    file TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    rule_id TEXT NOT NULL,
    masked TEXT NOT NULL,
    hash TEXT NOT NULL,
    action TEXT NOT NULL,
    UNIQUE (repo, file, line_number, hash, action)
);
"""


def record_findings(findings: list[dict], repo: str, action: str) -> None:
    """action: 'reported' (DRY_RUN) or 'blocked'."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH, timeout=10) as con:
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute(SCHEMA)
        con.executemany(
            "INSERT OR IGNORE INTO findings(repo, file, line_number, rule_id, masked, hash, action) VALUES (?,?,?,?,?,?,?)",
            [
                (repo, f["file"], f["line_number"], f["rule_id"], f["masked_secret"], f["hashed_secret"], action)
                for f in findings
            ],
        )