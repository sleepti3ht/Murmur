# murmur/external_scan.py
"""
External repository scanner.
Scans public GitHub repositories without cloning them locally.
Uses temporary directory and automatic cleanup.

Usage: python -m murmur.external_scan <repo_url> [--max-commits N]
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from murmur.adapters.history import HistoryAdapter
from murmur.core.detector import SecretDetector
from murmur.alerting.console import ConsoleAlerter
from murmur.storage.sqlite import record_findings, record_log, record_run


def parse_github_url(url: str) -> tuple[str, str]:
    """
    Parse GitHub URL and return (owner, repo_name).
    
    Examples:
        https://github.com/owner/repo -> ("owner", "repo")
        git@github.com:owner/repo.git -> ("owner", "repo")
        owner/repo -> ("owner", "repo")
    """
    # Handle SSH URLs
    if url.startswith("git@github.com:"):
        url = url.replace("git@github.com:", "")
    
    # Handle HTTPS URLs
    if url.startswith("https://github.com/"):
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        parts = path.split("/")
        if len(parts) >= 2:
            return parts[0], parts[1].replace(".git", "")
    
    # Handle bare "owner/repo" format
    if "/" in url:
        parts = url.strip("/").split("/")
        return parts[0], parts[1].replace(".git", "")
    
    raise ValueError(f"Invalid GitHub URL: {url}")


def clone_repo_temporarily(owner: str, repo: str, depth: int = 1) -> Path:
    """
    Clone repository to temporary directory.
    Returns path to cloned repo.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix=f"murmur_{repo}_"))
    repo_url = f"https://github.com/{owner}/{repo}.git"
    
    print(f"[MURMUR] Cloning {owner}/{repo} to temporary directory...")
    print(f"[MURMUR] Temp path: {temp_dir}")
    
    try:
        subprocess.run(
            ["git", "clone", "--depth", str(depth), "--quiet", repo_url, str(temp_dir)],
            check=True,
            capture_output=True,
            timeout=60,
        )
        return temp_dir
    except subprocess.CalledProcessError as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"Failed to clone repository: {e.stderr.decode()}")
    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError("Repository clone timed out (60s limit)")


def scan_external_repo(
    repo_url: str,
    max_commits: int = 100,
    use_history: bool = True,
) -> int:
    """
    Scan external GitHub repository for secrets.
    
    Args:
        repo_url: GitHub repository URL or owner/repo
        max_commits: Maximum number of commits to scan
        use_history: If True, scan full history; if False, scan only HEAD
    
    Returns:
        Exit code: 0 if no secrets found, 1 if secrets detected
    """
    import time
    
    started = time.perf_counter()
    temp_path = None
    
    try:
        # Parse URL
        owner, repo_name = parse_github_url(repo_url)
        full_name = f"{owner}/{repo_name}"
        
        print(f"[MURMUR] External scan: {full_name}")
        print(f"[MURMUR] Mode: {'Full history' if use_history else 'HEAD only'}")
        print("=" * 70)
        
        # Clone to temp directory
        temp_path = clone_repo_temporarily(owner, repo_name, depth=max_commits if use_history else 1)
        
        # Load allowlist (from current directory or default)
        allowlist_file = Path("allowlist.txt")
        allowlist = allowlist_file.read_text().splitlines() if allowlist_file.exists() else []
        
        # Scan repository
        if use_history:
            adapter = HistoryAdapter(
                repo_path=temp_path,
                max_commits=max_commits,
                timeout_sec=300,
            )
            print(f"[MURMUR] Scanning last {max_commits} commits...")
        else:
            # For HEAD-only scan, we could use GitHookAdapter with post-commit mode
            # But HistoryAdapter with max_commits=1 is simpler
            adapter = HistoryAdapter(
                repo_path=temp_path,
                max_commits=1,
                timeout_sec=60,
            )
            print("[MURMUR] Scanning HEAD...")
        
        changes = adapter.get_changes()
        print(f"[MURMUR] Analyzing {len(changes)} lines...")
        
        # Run detector
        detector = SecretDetector(allowlist=allowlist, dry_run=True)
        findings = detector.analyze(changes)
        
        # Record results
        duration_ms = int((time.perf_counter() - started) * 1000)
        record_run(
            str(full_name),
            "external_scan",
            True,
            len({c["file"] for c in changes}),
            len(findings),
            duration_ms,
            "completed",
        )
        
        if findings:
            record_findings(findings, repo=full_name, action="external")
        
        # Output results
        print("\n" + "=" * 70)
        alerter = ConsoleAlerter()
        alerter.notify(findings)
        
        print(f"\n[MURMUR] Scan completed in {duration_ms}ms")
        print(f"[MURMUR] Found {len(findings)} potential secrets")
        
        return 1 if findings else 0
        
    except Exception as e:
        print(f"\n[MURMUR] Error: {e}", file=sys.stderr)
        return 2
        
    finally:
        # Cleanup temporary directory
        if temp_path and temp_path.exists():
            try:
                shutil.rmtree(temp_path, ignore_errors=True)
                print(f"[MURMUR] Cleaned up temporary files")
            except Exception as e:
                print(f"[MURMUR] Warning: Failed to cleanup temp files: {e}")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python -m murmur.external_scan <repo_url> [--max-commits N]")
        print("\nExamples:")
        print("  python -m murmur.external_scan https://github.com/owner/repo")
        print("  python -m murmur.external_scan owner/repo")
        print("  python -m murmur.external_scan owner/repo --max-commits 50")
        return 1
    
    repo_url = sys.argv[1]
    max_commits = 100
    
    # Parse optional arguments
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--max-commits" and i + 1 < len(sys.argv):
            max_commits = int(sys.argv[i + 1])
    
    return scan_external_repo(repo_url, max_commits=max_commits)


if __name__ == "__main__":
    sys.exit(main())