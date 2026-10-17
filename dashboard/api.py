# dashboard/api.py
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from murmur.storage.sqlite import recent_runs, recent_findings
from murmur.external_scan import scan_external_repo

app = FastAPI(title="Murmur Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["tauri://localhost",
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://localhost:1430",
        "http://127.0.0.1:1430"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScanRequest(BaseModel):
    repo_url: str
    max_commits: int = 100

# Mock custom rules for v1.8 groundwork
CUSTOM_RULES = [
    {"id": "custom.telegram_bot", "pattern": r"\d{10}:[A-Za-z0-9_-]{35}", "severity": "high", "active": True},
    {"id": "custom.stripe_key", "pattern": r"sk_live_[A-Za-z0-9]{24,}", "severity": "high", "active": True},
]

@app.get("/api/status")
async def get_status():
    return {"status": "ok", "version": "1.9.0"}

@app.get("/api/findings")
async def get_findings(limit: int = 50):
    try:
        findings = recent_findings(limit)
        return [dict(f) for f in findings]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/runs")
async def get_runs(limit: int = 20):
    try:
        runs = recent_runs(limit)
        return [dict(r) for r in runs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/rules")
async def get_custom_rules():
    return {"rules": CUSTOM_RULES}

@app.post("/api/scan")
async def trigger_scan(request: ScanRequest):
    try:
        exit_code = scan_external_repo(request.repo_url, max_commits=request.max_commits, use_history=True)
        return {"success": exit_code == 0, "exit_code": exit_code}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")