from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import PurePosixPath

from murmur.core.models import ChangeLine, DetectionResult

@dataclass(frozen=True)
class Rule:
    rule_id: str
    pattern: re.Pattern[str]
    severity: str = "high"
    secret_group: int = 0

RULES: tuple[Rule, ...] = (
    Rule(rule_id="aws.access_key_id", pattern=re.compile(r"\b(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b")),
    Rule(rule_id="github.token", pattern=re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b")),
    Rule(rule_id="slack.token", pattern=re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,250}\b")),
    Rule(rule_id="private_key", pattern=re.compile(r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|PGP) PRIVATE KEY-----")),
    # ... existing code ... (Add more provider-specific regex rules here)
    Rule(
        rule_id="generic.secret",
        pattern=re.compile(r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|password)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-./+=]{16,128})['\"]?"),
        secret_group=1, severity="medium"
    ),
)

class SecretDetector:
    HEX64_RE = re.compile(r"^[a-fA-F0-9]{64}$")
    PLACEHOLDER_EXACT = {"example", "dummy", "test", "changeme", "placeholder", "your_token", "secret", "password"}

    def __init__(self, allowlist: list[str] | None = None, dry_run: bool | None = None) -> None:
        self.dry_run = os.getenv("DRY_RUN", "1").lower() not in {"0", "false", "no", "off"} if dry_run is None else dry_run
        self.path_allowlist: set[str] = set()
        self.hash_allowlist: set[str] = set()

        for item in (allowlist or []):
            item = item.strip()
            if not item or item.startswith("#"): continue
            if self.HEX64_RE.match(item): self.hash_allowlist.add(item.lower())
            else: self.path_allowlist.add(PurePosixPath(item).as_posix())

    def analyze(self, lines: list[dict]) -> list[dict]:
        findings: list[dict] = []
        for raw_line in lines:
            line = ChangeLine.model_validate(raw_line)
            if self._is_path_allowed(line.file): continue

            candidate_hash = self._sha256(line.content)
            if candidate_hash in self.hash_allowlist: continue

            for rule in RULES:
                match = rule.pattern.search(line.content)
                if not match: continue

                secret = match.group(rule.secret_group).strip().strip("'\"")
                if not secret or self._is_placeholder(secret): continue

                secret_hash = self._sha256(secret)
                if secret_hash in self.hash_allowlist: continue

                findings.append(DetectionResult(
                    file=line.file, line_number=line.line_number, rule_id=rule.rule_id,
                    severity=rule.severity, hashed_secret=secret_hash, masked_secret=self._mask(secret)
                ).model_dump())
                break # Stop at first match per line for MVP
        return findings

    def _is_path_allowed(self, path: str) -> bool:
        p = PurePosixPath(path).as_posix()
        return any(p == pat or p.startswith(pat + "/") or fnmatch(p, pat) for pat in self.path_allowlist)

    def _is_placeholder(self, value: str) -> bool:
        low = value.lower()
        return low in self.PLACEHOLDER_EXACT or (value.startswith("${") and value.endswith("}"))

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()

    @staticmethod
    def _mask(value: str) -> str:
        return f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "*" * len(value)