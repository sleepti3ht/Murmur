import sys
from pathlib import Path
from murmur.adapters.git_hook import GitHookAdapter, AdapterError
from murmur.core.detector import SecretDetector
from murmur.alerting.console import ConsoleAlerter

def main() -> int:
    try:
        adapter = GitHookAdapter(repo_path=Path.cwd(), hook_type="pre-commit")
        changes = adapter.get_changes()
    except AdapterError as e:
        print(f"[MURMUR] Adapter failed: {e}", file=sys.stderr)
        return 0 # Fail-open for MVP to not block developer workflow on git errors

    # Load allowlist
    allowlist_file = Path("allowlist.txt")
    allowlist = allowlist_file.read_text().splitlines() if allowlist_file.exists() else []

    detector = SecretDetector(allowlist=allowlist)
    findings = detector.analyze(changes)

    alerter = ConsoleAlerter()
    alerter.notify(findings)

    if findings and not detector.dry_run:
        return 1 # Block commit if secrets found and DRY_RUN=0
        
    return 0

if __name__ == "__main__":
    sys.exit(main())