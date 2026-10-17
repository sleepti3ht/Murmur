# murmur/storage/sqlite.py
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".murmur" / "findings.db"

FINDINGS_SCHEMA = """
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
    confidence TEXT NOT NULL DEFAULT 'medium',
    commit_sha TEXT,
    author TEXT,
    UNIQUE (repo, file, line_number, hash, action)
);
"""

RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    repo TEXT NOT NULL,
    mode TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    files_scanned INTEGER NOT NULL,
    findings_count INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    action TEXT NOT NULL
);
"""


def _ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH, timeout=10) as con:
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute(FINDINGS_SCHEMA)
        con.execute(RUNS_SCHEMA)


def record_findings(findings: list[dict], repo: str, action: str) -> None:
    """action: 'reported' (DRY_RUN) or 'blocked'."""
    _ensure_db()
    with sqlite3.connect(DB_PATH, timeout=10) as con:
        con.execute("PRAGMA journal_mode=WAL;")
        con.executemany(
            "INSERT OR IGNORE INTO findings(repo, file, line_number, rule_id, masked, hash, action, confidence, commit_sha, author) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    repo,
                    f["file"],
                    f["line_number"],
                    f["rule_id"],
                    f["masked_secret"],
                    f["hashed_secret"],
                    action,
                    f.get("confidence", "medium"),
                    f.get("commit_sha"),
                    f.get("author"),
                )
                for f in findings
            ],
        )


def record_run(
    repo: str,
    mode: str,
    dry_run: bool,
    files_scanned: int,
    findings_count: int,
    duration_ms: int,
    action: str,
) -> None:
    """action: 'passed' | 'reported' | 'blocked' | 'adapter_error'."""
    _ensure_db()
    with sqlite3.connect(DB_PATH, timeout=10) as con:
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute(
            "INSERT INTO runs(repo, mode, dry_run, files_scanned, findings_count, duration_ms, action) "
            "VALUES (?,?,?,?,?,?,?)",
            (repo, mode, int(dry_run), files_scanned, findings_count, duration_ms, action),
        )


def recent_runs(limit: int = 20) -> list[sqlite3.Row]:
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row
        if not con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='runs'"
        ).fetchone():
            return []
        return con.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


def recent_findings(limit: int = 50) -> list[sqlite3.Row]:
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row
        if not con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='findings'"
        ).fetchone():
            return []
        return con.execute(
            "SELECT * FROM findings ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()