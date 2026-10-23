# murmur/adapters/history.py
"""
History adapter for scanning full repository history.
Uses `git log -p` to extract all changes across commits.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from murmur.adapters.base import BaseAdapter
from murmur.core.models import ChangeLine


class HistoryAdapter(BaseAdapter):
    """
    Scans repository history for secrets.
    Useful for one-time audits when onboarding a new project.
    """

    # Matches hunk header with optional trailing context after @@
    HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@.*")

    def __init__(
        self,
        repo_path: Path | str = Path.cwd(),
        max_commits: int = 100,
        timeout_sec: int = 300,
        max_line_length: int = 5000,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.max_commits = max_commits
        self.timeout_sec = timeout_sec
        self.max_line_length = max_line_length

    def get_changes(self) -> list[dict]:
        """
        Scan repository history and return all added lines.
        """
        proc = self._run_git([
            "log", "-p",
            f"-n {self.max_commits}",
            "--no-color",
            "--unified=0",
        ])

        if proc.returncode != 0:
            print(f"[MURMUR] git log failed: {proc.stderr.decode()}", file=sys.stderr)
            return []

        diff_text = self._decode(proc.stdout)
        return self._parse_history_diff(diff_text)

    def _parse_history_diff(self, diff_text: str) -> list[dict]:
        """
        Parse git log -p output and extract added lines with commit attribution.
        """
        current_file: str | None = None
        line_number: int | None = None
        commit_sha: str | None = None
        author: str | None = None
        commit_ts: str | None = None
        changes: list[dict] = []

        for raw_line in diff_text.splitlines():
            # Commit metadata headers emitted by `git log -p`
            if raw_line.startswith("commit "):
                commit_sha = raw_line.split()[1]
                author = None
                commit_ts = None
                continue
            if raw_line.startswith("Author: "):
                author = raw_line[len("Author: "):].strip()
                continue
            if raw_line.startswith("Date: "):
                commit_ts = raw_line[len("Date: "):].strip()
                continue
            # New file header resets context
            if raw_line.startswith("diff --git "):
                current_file = None
                line_number = None
                continue

            # Target file
            if raw_line.startswith("+++ "):
                target = self._extract_diff_path(raw_line[4:])
                current_file = target if target else None
                continue

            # Hunk header sets the starting line number
            hunk = self.HUNK_RE.match(raw_line)
            if hunk:
                line_number = int(hunk.group(1))
                continue

            # Added line
            if current_file and line_number and raw_line.startswith("+"):
                content = raw_line[1:].rstrip("\r")
                if 0 < len(content) <= self.max_line_length:
                    changes.append(
                        ChangeLine(
                            file=current_file,
                            line_number=line_number,
                            content=content,
                            commit_sha=commit_sha,
                            author=author,
                            commit_ts=commit_ts,
                        ).model_dump()
                    )
                line_number += 1
            elif raw_line.startswith(" "):
                if line_number:
                    line_number += 1

        return changes

    def _extract_diff_path(self, raw: str) -> str:
        target = raw.strip().strip('"')
        target = target.removeprefix("b/")
        return target

    def _decode(self, data: bytes) -> str:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("latin-1")

    def _run_git(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
        cmd = ["git", "-C", str(self.repo_path), *args]
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(cmd, 1, b"", b"timeout")
        return proc
