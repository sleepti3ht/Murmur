from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Iterable, Literal

from murmur.adapters.base import BaseAdapter
from murmur.core.models import ChangeLine

class AdapterError(RuntimeError):
    pass

class GitHookAdapter(BaseAdapter):
    # Git empty tree SHA. Used for the initial commit.
    EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee490457a39f4d"
    HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

    def __init__(
        self,
        repo_path: Path | str = Path.cwd(),
        hook_type: Literal["pre-commit", "post-commit"] = "pre-commit",
        timeout_sec: int = 30,
        max_line_length: int = 5000,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.hook_type = hook_type
        self.timeout_sec = timeout_sec
        self.max_line_length = max_line_length

    def get_changes(self) -> list[dict]:
        changed_files = self._changed_files()
        if not changed_files:
            return []

        binary_files = self._binary_files()
        allowed_files = changed_files - binary_files

        if not allowed_files:
            return []

        diff_proc = self._run_git(
            ["diff", "--no-pager", "--unified=0", "--no-color", "--diff-filter=ACMR"]
        )
        
        diff_text = self._decode(diff_proc.stdout)
        return self._parse_diff(diff_text, allowed_files)

    def _changed_files(self) -> set[str]:
        proc = self._run_git(["diff", "--no-pager", "--name-only", "-z", "--diff-filter=ACMR"])
        return {self._normalize_path(p) for p in proc.stdout.split(b"\0") if p}

    def _binary_files(self) -> set[str]:
        # Git marks binary files in numstat as: "-\t-\tpath/to/file"
        proc = self._run_git(["diff", "--no-pager", "--numstat", "-z", "--diff-filter=ACMR"])
        result = set()
        for raw in proc.stdout.split(b"\0"):
            if not raw: continue
            parts = self._decode(raw).split("\t", 2)
            if len(parts) == 3 and (parts[0].strip() == "-" or parts[1].strip() == "-"):
                result.add(self._normalize_path(parts[2]))
        return result

    def _parse_diff(self, diff_text: str, allowed_files: set[str]) -> list[dict]:
        current_file: str | None = None
        line_number: int | None = None
        changes: list[dict] = []

        for raw_line in diff_text.splitlines():
            if raw_line.startswith("+++ "):
                target = self._extract_diff_path(raw_line[4:])
                current_file = target if target in allowed_files else None
                continue

            hunk = self.HUNK_RE.match(raw_line)
            if hunk:
                line_number = int(hunk.group(1))
                continue

            if current_file and line_number and raw_line.startswith("+"):
                content = raw_line[1:].rstrip("\r")
                if 0 < len(content) <= self.max_line_length:
                    changes.append(
                        ChangeLine(file=current_file, line_number=line_number, content=content).model_dump()
                    )
                line_number += 1
            elif raw_line.startswith(" "):
                if line_number: line_number += 1

        return changes

    def _extract_diff_path(self, raw: str) -> str:
        target = raw.strip().strip('"')
        if target.startswith("b/"): target = target[2:]
        return self._normalize_path(target)

    def _normalize_path(self, path: str | bytes) -> str:
        if isinstance(path, bytes): path = self._decode(path)
        return Path(path.strip()).as_posix()

    def _decode(self, data: bytes) -> str:
        # Fallback to latin-1 to preserve byte alignment if UTF-8 fails
        try: return data.decode("utf-8")
        except UnicodeDecodeError: return data.decode("latin-1")

    def _run_git(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
        cmd = ["git", "-C", str(self.repo_path)]
        
        # Handle initial commit edge case
        if args[0] == "diff" and not self._head_exists():
            args.append(self.EMPTY_TREE)
            
        cmd.extend(args)

        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=self.timeout_sec, check=False)
        except subprocess.TimeoutExpired as exc:
            raise AdapterError("git timeout") from exc
            
        if proc.returncode != 0:
            raise AdapterError(f"git returned {proc.returncode}")
        return proc

    def _head_exists(self) -> bool:
        proc = subprocess.run(["git", "-C", str(self.repo_path), "rev-parse", "--verify", "HEAD"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc.returncode == 0