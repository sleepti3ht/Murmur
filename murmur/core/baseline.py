# murmur/core/baseline.py
"""
Baseline snapshot of known findings for legacy repository onboarding.

Stores SHA-256 hashes of secrets accepted as technical debt. Subsequent
scans suppress baselined findings and alert only on newly introduced ones.
"""
from __future__ import annotations

import json
from pathlib import Path

BASELINE_NAME = ".murmur-baseline.json"


def baseline_path(repo_path: Path) -> Path:
    return Path(repo_path) / BASELINE_NAME


def load_baseline(repo_path: Path) -> set[str]:
    """Return baseline hashes; tolerate missing or corrupt snapshot."""
    path = baseline_path(repo_path)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("hashes", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_baseline(repo_path: Path, hashes: set[str]) -> Path:
    path = baseline_path(repo_path)
    payload = {"version": 1, "hashes": sorted(hashes)}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path