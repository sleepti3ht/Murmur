# murmur/status.py
"""
Murmur Status Dashboard.
Displays recent Git commits and Murmur scan history for the current repository.
Usage: python -m murmur.status
"""
import subprocess
from pathlib import Path

from murmur.storage.sqlite import recent_findings, recent_runs


def get_recent_commits(repo_path: Path, limit: int = 5) -> list[str]:
    """Fetch recent git commits using subprocess."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "log", f"-n {limit}", "--oneline", "--decorate"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().split("\n")
    except subprocess.CalledProcessError:
        return ["Not a git repository or no commits yet."]


def main() -> None:
    repo_path = Path.cwd().resolve()

    print("=" * 70)
    print(f" 🌑 MURMUR STATUS | {repo_path.name}")
    print("=" * 70)

    # 1. Recent Git Commits
    print("\n📌 Recent Git Commits:")
    commits = get_recent_commits(repo_path, 5)
    for commit in commits:
        print(f"  • {commit}")

    # 2. Recent Murmur Runs
    print("\n🛡️ Recent Murmur Scans:")
    runs = recent_runs(5)
    # Filter runs for current repo
    repo_str = str(repo_path)
    repo_runs = [r for r in runs if repo_str in r['repo']]

    if not repo_runs:
        print("  • No scan history found for this repository.")
    else:
        for run in repo_runs:
            status_icon = "✅" if run['action'] == 'passed' else "🚨"
            print(f"  {status_icon} [{run['ts']}] {run['action'].upper():<8} | "
                  f"Files: {run['files_scanned']:<3} | Findings: {run['findings_count']:<2} | "
                  f"Time: {run['duration_ms']}ms")

    # 3. Recent Findings
    print("\n🔍 Recent Findings (Last 5):")
    findings = recent_findings(5)
    repo_findings = [f for f in findings if repo_str in f['repo']]

    if not repo_findings:
        print("  • No secrets detected recently.")
    else:
        for f in repo_findings:
            conf_marker = {"high": "[!]", "medium": "[*]", "low": "[.]"}.get(f['confidence'], "[ ]")
            print(f"  {conf_marker} {f['file']}:{f['line_number']} | "
                  f"Rule: {f['rule_id']:<20} | Mask: {f['masked']}")

    print("=" * 70)


if __name__ == "__main__":
    main()
