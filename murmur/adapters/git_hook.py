from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Literal

from murmur.adapters.base import BaseAdapter
from murmur.core.models import ChangeLine


class AdapterError(RuntimeError):
    pass


class GitHookAdapter(BaseAdapter):
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
        ignored_files = self._ignored_files(changed_files - binary_files)
        allowed_files = (changed_files - binary_files) - ignored_files

        if not allowed_files:
            return []

        diff_proc = self._run_git(
            self._diff_args(["--unified=0", "--no-color", "--diff-filter=ACMR"])
        )
        diff_text = self._decode(diff_proc.stdout)
        return self._parse_diff(diff_text, allowed_files)

    def _changed_files(self) -> set[str]:
        proc = self._run_git(self._diff_args(["--name-only", "-z", "--diff-filter=ACMR"]))
        return {
            self._normalize_path(self._decode(p))
            for p in proc.stdout.split(b"\0")
            if p
        }

    def _binary_files(self) -> set[str]:
        proc = self._run_git(self._diff_args(["--numstat", "-z", "--diff-filter=ACMR"]))
        result: set[str] = set()
        for raw in proc.stdout.split(b"\0"):
            if not raw:
                continue
            parts = self._decode(raw).split("\t", 2)
            if len(parts) == 3 and (parts[0].strip() == "-" or parts[1].strip() == "-"):
                result.add(self._normalize_path(parts[2]))
        return result

    def _ignored_files(self, paths: set[str]) -> set[str]:
        if not paths:
            return set()
        stdin_data = (
            b"\0".join(p.encode("utf-8", "surrogatepass") for p in sorted(paths)) + b"\0"
        )
        proc = self._run_git(
            ["check-ignore", "--no-index", "-z", "--stdin"],
            input_bytes=stdin_data,
            ok_exit=(0, 1),
        )
        return {
            self._normalize_path(self._decode(p))
            for p in proc.stdout.split(b"\0")
            if p
        }

    def _diff_args(self, extra: list[str]) -> list[str]:
        if self.hook_type == "pre-commit":
            # git diff --cached natively handles unborn HEAD (initial commit).
            return ["diff", "--cached", *extra]

        parent = self._parent_ref()
        if parent:
            return ["diff", *extra, parent, "HEAD"]

        # Root commit in post-commit: git show diffs against empty tree natively.
        return ["show", "--format=", *extra, "HEAD"]

    def _parent_ref(self) -> str | None:
        cmd = ["git", "-C", str(self.repo_path), "rev-parse", "--verify", "HEAD~1"]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=self.timeout_sec,
            check=False,
        )
        return "HEAD~1" if proc.returncode == 0 else None

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
                if line_number:
                    line_number += 1

        return changes

    def _extract_diff_path(self, raw: str) -> str:
        target = raw.strip().strip('"')
        if target.startswith("b/"):
            target = target[2:]
        return self._normalize_path(target)

    def _normalize_path(self, path: str | bytes) -> str:
        if isinstance(path, bytes):
            path = self._decode(path)
        return Path(path.strip()).as_posix()

    def _decode(self, data: bytes) -> str:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("latin-1")

    def _run_git(
        self,
        args: list[str],
        input_bytes: bytes | None = None,
        ok_exit: tuple[int, ...] = (0,),
    ) -> subprocess.CompletedProcess[bytes]:
        cmd = ["git", "-C", str(self.repo_path), *args]
        try:
            proc = subprocess.run(
                cmd,
                input=input_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdapterError("git timeout") from exc

        if proc.returncode not in ok_exit:
            stderr_tail = proc.stderr.decode("utf-8", errors="replace").strip()[-500:]
            raise AdapterError(f"git returned {proc.returncode}: {stderr_tail}")

        return proc