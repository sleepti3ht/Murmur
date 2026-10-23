# dashboard/api.py
"""Local API server for the Murmur Dashboard."""
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from murmur.core.detector import RULES, Rule, SecretDetector, _load_custom_rules
from murmur.core.entropy import shannon_entropy
from murmur.core.scoring import compute_confidence
from murmur.storage.sqlite import recent_findings, recent_logs, recent_runs

app = FastAPI(title="Murmur Dashboard API")

# Local dev origins (Tauri dev server port may vary between runs)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "tauri://localhost",
        "http://tauri.localhost",
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://localhost:1430",
        "http://127.0.0.1:1430",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RULES_FILE = Path.home() / ".murmur" / "custom_rules.yaml"
VALID_SEVERITIES = {"high", "medium", "low"}


class RuleRequest(BaseModel):
    id: str = Field(min_length=3)
    pattern: str = Field(min_length=1)
    severity: str = "medium"
    description: str = ""


class PlaygroundRequest(BaseModel):
    text: str
    pattern: str | None = None


def load_custom_rules() -> list[dict]:
    """Read custom rules from YAML; tolerate missing or corrupt file."""
    if not RULES_FILE.exists():
        return []
    try:
        data = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8")) or {}
        return data.get("rules", [])
    except yaml.YAMLError:
        return []


def save_custom_rules(rules: list[dict]) -> None:
    """Atomic write: temp file + os.replace prevents torn reads by the hook."""
    RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=RULES_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump({"rules": rules}, f, sort_keys=False)
        os.replace(tmp_path, RULES_FILE)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


@app.get("/api/status")
async def get_status():
    return {"status": "ok", "version": "1.9.0"}


@app.get("/api/findings")
async def get_findings(limit: int = 100):
    return [dict(f) for f in recent_findings(limit)]


@app.get("/api/runs")
async def get_runs(limit: int = 100):
    return [dict(r) for r in recent_runs(limit)]


@app.get("/api/logs")
async def get_logs(limit: int = 200):
    """Return recent hook/application log rows for the dashboard Logs tab."""
    return {"logs": [dict(r) for r in recent_logs(limit)]}

@app.get("/api/rules")
async def get_rules():
    return {"rules": load_custom_rules()}


@app.post("/api/rules", status_code=201)
async def add_rule(rule: RuleRequest):
    """Create a custom detection rule after validating id, severity and regex."""
    if rule.severity not in VALID_SEVERITIES:
        raise HTTPException(status_code=422, detail="Invalid severity")
    try:
        re.compile(rule.pattern)
    except re.error as e:
        raise HTTPException(status_code=422, detail=f"Invalid regex: {e}")

    rules = load_custom_rules()
    if any(r.get("id") == rule.id for r in rules):
        raise HTTPException(status_code=409, detail="Rule ID already exists")

    rules.append(
        {
            "id": rule.id,
            "pattern": rule.pattern,
            "severity": rule.severity,
            "description": rule.description,
            "active": True,
        }
    )
    save_custom_rules(rules)
    return {"rules": rules}


@app.delete("/api/rules/{rule_id}")
async def delete_rule(rule_id: str):
    rules = load_custom_rules()
    filtered = [r for r in rules if r.get("id") != rule_id]
    if len(filtered) == len(rules):
        raise HTTPException(status_code=404, detail="Rule not found")
    save_custom_rules(filtered)
    return {"rules": filtered}


@app.post("/api/playground")
async def playground(request: PlaygroundRequest):
    """Test arbitrary text against active rules plus an optional one-off regex."""
    rules = list(RULES) + _load_custom_rules()
    if request.pattern:
        try:
            compiled = re.compile(request.pattern)
        except re.error as e:
            raise HTTPException(status_code=422, detail=f"Invalid regex: {e}")
        rules.append(
            Rule(
                rule_id="playground.oneoff",
                pattern=compiled,
                severity="medium",
                secret_group=1 if compiled.groups else 0,
            )
        )

    detector = SecretDetector()
    results = []
    for rule in rules:
        match = rule.pattern.search(request.text)
        if not match:
            continue
        secret = match.group(rule.secret_group).strip().strip("'\"")
        if not secret or detector._is_placeholder(secret):
            continue
        results.append(
            {
                "rule_id": rule.rule_id,
                "masked": SecretDetector._mask(secret),
                "entropy": round(shannon_entropy(secret), 2),
                "confidence": compute_confidence(rule.rule_id, secret),
                "severity": rule.severity,
            }
        )
    return {"results": results}


@app.post("/api/scan")
async def trigger_scan(repo_url: str, max_commits: int = 100):
    """Lazy import keeps startup light; scan runs synchronously in this MVP."""
    from murmur.external_scan import scan_external_repo

    exit_code = scan_external_repo(repo_url, max_commits=max_commits, use_history=True)
    return {"success": exit_code == 0, "exit_code": exit_code}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
