# murmur/baseline.py
"""
Baseline management CLI.

Usage:
    python -m murmur.baseline create [repo_path]
    python -m murmur.baseline show [repo_path]
"""
import sys
from pathlib import Path

from murmur.adapters.git_push import EMPTY_TREE, PrePushAdapter
from murmur.core.baseline import baseline_path, load_baseline, save_baseline
from murmur.core.detector import SecretDetector


def _allowlist(repo_path: Path) -> list[str]:
    f = repo_path / "allowlist.txt"
    return f.read_text(encoding="utf-8").splitlines() if f.exists() else []


def create(repo_path: Path) -> int:
    """Snapshot hashes of all secrets currently present in the HEAD tree."""
    changes = PrePushAdapter(repo_path=repo_path).diff_added_lines(f"{EMPTY_TREE}..HEAD")
    findings = SecretDetector(allowlist=_allowlist(repo_path)).analyze(changes)
    hashes = {f["hashed_secret"] for f in findings}
    path = save_baseline(repo_path, hashes)
    print(f"[MURMUR] Baseline created: {len(hashes)} hash(es) -> {path}")
    return 0


def show(repo_path: Path) -> int:
    hashes = load_baseline(repo_path)
    print(f"[MURMUR] Baseline at {baseline_path(repo_path)}: {len(hashes)} hash(es)")
    for h in sorted(hashes):
        print(f"  {h}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    command = args[0] if args else "show"
    repo = Path(args[1]).resolve() if len(args) > 1 else Path.cwd()
    if command == "create":
        return create(repo)
    if command == "show":
        return show(repo)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())