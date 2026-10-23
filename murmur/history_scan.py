# murmur/history_scan.py
"""
History scan CLI: scans repository history for secrets.
Usage: python -m murmur.history_scan [repo_path] [--max-commits N]
"""
import sys
import time
from pathlib import Path

from murmur.adapters.history import HistoryAdapter
from murmur.alerting.console import ConsoleAlerter
from murmur.core.detector import SecretDetector
from murmur.storage.sqlite import record_findings, record_run


def main() -> int:
    started = time.perf_counter()

    # Parse arguments
    repo_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    max_commits = 100

    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--max-commits" and i + 1 < len(sys.argv):
            max_commits = int(sys.argv[i + 1])

    print(f"[MURMUR] Scanning history of {repo_path} (last {max_commits} commits)...")

    # Run history adapter
    adapter = HistoryAdapter(repo_path=repo_path, max_commits=max_commits)
    changes = adapter.get_changes()

    print(f"[MURMUR] Analyzing {len(changes)} lines from history...")

    # Load allowlist
    allowlist_file = Path("allowlist.txt")
    allowlist = allowlist_file.read_text().splitlines() if allowlist_file.exists() else []

    # Run detector
    detector = SecretDetector(allowlist=allowlist, dry_run=True)
    findings = detector.analyze(changes)

    # Record results
    duration_ms = int((time.perf_counter() - started) * 1000)
    record_run(
        str(repo_path), "history_scan", True,
        len({c["file"] for c in changes}), len(findings), duration_ms, "completed",
    )

    if findings:
        record_findings(findings, repo=str(repo_path), action="historical")

    # Output results
    alerter = ConsoleAlerter()
    alerter.notify(findings)

    print(f"\n[MURMUR] History scan completed in {duration_ms}ms")
    print(f"[MURMUR] Found {len(findings)} potential secrets in history")

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
