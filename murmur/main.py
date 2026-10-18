# murmur/main.py
"""Entry point for local Git hooks (pre-commit and pre-push)."""
import sys
import time
from pathlib import Path

from murmur.adapters.git_hook import AdapterError, GitHookAdapter
from murmur.adapters.git_push import PrePushAdapter
from murmur.alerting.console import ConsoleAlerter
from murmur.core.baseline import load_baseline
from murmur.core.detector import SecretDetector
from murmur.storage.sqlite import record_findings, record_log, record_run


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _parse_args(argv: list[str]) -> tuple[Path, str]:
    positional = [a for a in argv[1:] if not a.startswith("--")]
    repo = Path(positional[0]).resolve() if positional else Path.cwd()
    mode = "pre-commit"
    for arg in argv[1:]:
        if arg.startswith("--mode="):
            mode = arg.split("=", 1)[1]
    return repo, mode


def main() -> int:
    started = time.perf_counter()
    repo_path, mode = _parse_args(sys.argv)

    if mode == "pre-push":
        # Git feeds ref specs via stdin: <local_ref> <local_sha> <remote_ref> <remote_sha>
        adapter = PrePushAdapter(repo_path=repo_path)
        pairs = adapter.parse_ref_specs(sys.stdin.read())
        changes = adapter.get_changes(pairs)
    else:
        try:
            adapter = GitHookAdapter(repo_path=repo_path, hook_type="pre-commit")
            changes = adapter.get_changes()
        except AdapterError as e:
            print(f"[MURMUR] Adapter failed: {e}", file=sys.stderr)
            record_log("error", mode, f"adapter failed: {e}", repo=str(repo_path))
            record_run(str(repo_path), mode, True, 0, 0, _ms(started), "adapter_error")
            return 0

    allowlist_file = repo_path / "allowlist.txt"
    allowlist = (
        allowlist_file.read_text(encoding="utf-8").splitlines()
        if allowlist_file.exists()
        else []
    )

    detector = SecretDetector(
        allowlist=allowlist,
        baseline_hashes=load_baseline(repo_path),
    )
    findings = detector.analyze(changes)
    record_log(
        "info",
        mode,
        f"scan completed: {len(changes)} lines analyzed, {len(findings)} findings",
        repo=str(repo_path),
    )
    if detector.baseline_skipped:
        print(f"[MURMUR] {detector.baseline_skipped} baseline-known finding(s) suppressed")
        record_log(
            "info",
            mode,
            f"{detector.baseline_skipped} baseline-known finding(s) suppressed",
            repo=str(repo_path),
        )
    action = "passed" if not findings else ("reported" if detector.dry_run else "blocked")
    record_run(
        str(repo_path),
        mode,
        detector.dry_run,
        len({c["file"] for c in changes}),
        len(findings),
        _ms(started),
        action,
    )
    record_log(
        "warning" if findings else "info",
        mode,
        f"action={action}, findings={len(findings)}, "
        f"files={len({c['file'] for c in changes})}, duration_ms={_ms(started)}",
        repo=str(repo_path),
    )
    if findings:
        record_findings(findings, repo=str(repo_path), action=action)

    ConsoleAlerter().notify(findings)

    if findings and not detector.dry_run:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())