# murmur/adapters/git_push.py
"""
Pre-push adapter: scans the net diff about to be sent to a remote.

Closes the local bypass gap (--no-verify, commit --amend) by validating
the exact commit range before it leaves the machine.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from murmur.core.models import ChangeLine

ZERO_SHA = "0" * 40
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


class PrePushAdapter:
    def __init__(
        self,
        repo_path: Path | str = Path.cwd(),
        timeout_sec: int = 120,
        max_line_length: int = 5000,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.timeout_sec = timeout_sec
        self.max_line_length = max_line_length

    @staticmethod
    def parse_ref_specs(stdin_text: str) -> list[tuple[str, str]]:
        """Extract (base, head) sha pairs from the pre-push stdin payload."""
        pairs: list[tuple[str, str]] = []
        for line in stdin_text.splitlines():
            parts = line.split()
            if len(parts) != 4:
                continue
            local_sha, remote_sha = parts[1], parts[3]
            if local_sha == ZERO_SHA:
                continue  # branch deletion, nothing to scan
            base = EMPTY_TREE if remote_sha == ZERO_SHA else remote_sha
            pairs.append((base, local_sha))
        return pairs

    def get_changes(self, pairs: list[tuple[str, str]]) -> list[dict]:
        """Aggregate added lines across ref pairs, deduplicated."""
        seen: set[tuple[str, int, str]] = set()
        changes: list[dict] = []
        for base, head in pairs:
            for change in self.diff_added_lines(f"{base}..{head}"):
                key = (change["file"], change["line_number"], change["content"])
                if key not in seen:
                    seen.add(key)
                    changes.append(change)
        return changes

    def diff_added_lines(self, rev_range: str) -> list[dict]:
        proc = self._run_git(["diff", "--no-color", "--unified=0", rev_range])
        if proc.returncode != 0:
            return []
        return self._parse_diff(self._decode(proc.stdout))

    def _parse_diff(self, diff_text: str) -> list[dict]:
        current_file: str | None = None
        line_number: int | None = None
        out: list[dict] = []
        for raw in diff_text.splitlines():
            if raw.startswith("diff --git "):
                current_file = None
                continue
            if raw.startswith("+++ "):
                target = raw[4:].strip().strip('"')
                current_file = target.removeprefix("b/")
                continue
            hunk = HUNK_RE.match(raw)
            if hunk:
                line_number = int(hunk.group(1))
                continue
            if current_file and line_number is not None and raw.startswith("+"):
                content = raw[1:].rstrip("\r")
                if 0 < len(content) <= self.max_line_length:
                    out.append(
                        ChangeLine(
                            file=current_file,
                            line_number=line_number,
                            content=content,
                        ).model_dump()
                    )
                line_number += 1
        return out

    def _decode(self, data: bytes) -> str:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("latin-1")

    def _run_git(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
        cmd = ["git", "-C", str(self.repo_path), *args]
        try:
            return subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(cmd, 1, b"", b"timeout")
