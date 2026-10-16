# murmur/main.py
import os
import sys
import time
from pathlib import Path

from murmur.adapters.git_hook import GitHookAdapter, AdapterError
from murmur.core.detector import SecretDetector
from murmur.alerting.console import ConsoleAlerter
from murmur.storage.sqlite import record_findings, record_run


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def main() -> int:
    started = time.perf_counter()
    repo_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    
    try:
        adapter = GitHookAdapter(repo_path=repo_path, hook_type="pre-commit")
        changes = adapter.get_changes()
    except AdapterError as e:
        print(f"[MURMUR] Adapter failed: {e}", file=sys.stderr)
        record_run(str(repo_path), "pre-commit", True, 0, 0, _ms(started), "adapter_error")
        return 0

    allowlist_file = Path("allowlist.txt")
    allowlist = allowlist_file.read_text().splitlines() if allowlist_file.exists() else []

    detector = SecretDetector(allowlist=allowlist)
    findings = detector.analyze(changes)

    action = "passed" if not findings else ("reported" if detector.dry_run else "blocked")
    record_run(
        str(repo_path), "pre-commit", detector.dry_run,
        len({c["file"] for c in changes}), len(findings), _ms(started), action,
    )

    if findings:
        record_findings(findings, repo=str(repo_path), action=action)

    alerter = ConsoleAlerter()
    alerter.notify(findings)

    if findings and not detector.dry_run:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())