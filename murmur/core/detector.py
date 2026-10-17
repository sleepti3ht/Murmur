# murmur/core/detector.py
from __future__ import annotations

import hashlib
import os
import re
import sys
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

import yaml

from murmur.core.models import ChangeLine, DetectionResult
from murmur.core.scoring import compute_confidence

CUSTOM_RULES_FILE = Path.home() / ".murmur" / "custom_rules.yaml"


@dataclass(frozen=True)
class Rule:
    """Detection rule definition."""
    rule_id: str
    pattern: re.Pattern[str]
    severity: str = "high"
    secret_group: int = 0


RULES: tuple[Rule, ...] = (
    Rule(
        rule_id="aws.access_key_id",
        pattern=re.compile(r"\b(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b"),
    ),
    Rule(
        rule_id="github.token",
        pattern=re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b"),
    ),
    Rule(
        rule_id="slack.token",
        pattern=re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,250}\b"),
    ),
    Rule(
        rule_id="private_key",
        pattern=re.compile(r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|PGP) PRIVATE KEY-----"),
    ),
    Rule(
        rule_id="generic.secret",
        pattern=re.compile(
            r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|password)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-./+=]{16,128})['\"]?"
        ),
        secret_group=1,
        severity="medium",
    ),
)


def _load_custom_rules() -> list[Rule]:
    """
    Load user-defined rules from ~/.murmur/custom_rules.yaml.

    Fail-open per rule: an invalid regex is skipped with a stderr warning
    so a single bad rule can never break the pre-commit workflow.
    Inactive rules (active: false) are ignored.
    """
    if not CUSTOM_RULES_FILE.exists():
        return []
    
    try:
        data = yaml.safe_load(CUSTOM_RULES_FILE.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError):
        return []

    rules: list[Rule] = []
    for entry in data.get("rules", []):
        if not entry.get("active", True):
            continue
        
        pattern_src = entry.get("pattern", "")
        try:
            compiled = re.compile(pattern_src)
        except re.error:
            print(
                f"[MURMUR] Skipping invalid custom rule: {entry.get('id')}",
                file=sys.stderr,
            )
            continue
        
        rules.append(
            Rule(
                rule_id=entry.get("id", "custom.unknown"),
                pattern=compiled,
                severity=entry.get("severity", "medium"),
                # Use capture group 1 when present, otherwise the whole match
                secret_group=1 if compiled.groups else 0,
            )
        )
    return rules


class SecretDetector:
    """Core engine for detecting secrets in code changes."""
    
    HEX64_RE = re.compile(r"^[a-fA-F0-9]{64}$")
    PLACEHOLDER_EXACT = {
        "example", "dummy", "test", "changeme", "placeholder", 
        "your_token", "secret", "password"
    }

    def __init__(self, allowlist: list[str] | None = None, dry_run: bool | None = None) -> None:
        if dry_run is None:
            self.dry_run = os.getenv("DRY_RUN", "1").lower() not in {"0", "false", "no", "off"}
        else:
            self.dry_run = dry_run
            
        self.path_allowlist: set[str] = set()
        self.hash_allowlist: set[str] = set()
        
        # Custom confidence overrides loaded from YAML
        self.confidence_overrides: dict[str, str] = {}

        for item in (allowlist or []):
            item = item.strip()
            if not item or item.startswith("#"):
                continue
            if self.HEX64_RE.match(item):
                self.hash_allowlist.add(item.lower())
            else:
                self.path_allowlist.add(PurePosixPath(item).as_posix())

        # Merge built-in rules with user-defined rules
        self.rules = list(RULES) + _load_custom_rules()
        
        # Load confidence overrides from the same YAML file
        self._load_confidence_overrides()

    def _load_confidence_overrides(self) -> None:
        """Load optional confidence overrides for custom rules."""
        if not CUSTOM_RULES_FILE.exists():
            return
        try:
            data = yaml.safe_load(CUSTOM_RULES_FILE.read_text(encoding="utf-8")) or {}
            for entry in data.get("rules", []):
                rule_id = entry.get("id")
                conf = entry.get("confidence")
                if rule_id and conf in {"high", "medium", "low"}:
                    self.confidence_overrides[rule_id] = conf
        except (yaml.YAMLError, OSError):
            pass

    def analyze(self, lines: list[dict]) -> list[dict]:
        """Analyze lines for potential secrets and return findings."""
        findings: list[dict] = []
        
        for raw_line in lines:
            line = ChangeLine.model_validate(raw_line)
            if self._is_path_allowed(line.file):
                continue

            candidate_hash = self._sha256(line.content)
            if candidate_hash in self.hash_allowlist:
                continue

            for rule in self.rules:
                match = rule.pattern.search(line.content)
                if not match:
                    continue

                secret = match.group(rule.secret_group).strip().strip("'\"")
                if not secret or self._is_placeholder(secret):
                    continue

                secret_hash = self._sha256(secret)
                if secret_hash in self.hash_allowlist:
                    continue

                # Determine confidence: use override if available, else compute
                if rule.rule_id in self.confidence_overrides:
                    confidence = self.confidence_overrides[rule.rule_id]
                else:
                    confidence = compute_confidence(rule.rule_id, secret)

                # Skip noise-level findings
                if confidence == "noise":
                    continue

                findings.append(
                    DetectionResult(
                        file=line.file,
                        line_number=line.line_number,
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        hashed_secret=secret_hash,
                        masked_secret=self._mask(secret),
                        confidence=confidence,
                    ).model_dump()
                )
                # Stop after first match per line to avoid duplicate alerts
                break
                
        return findings

    def _is_path_allowed(self, path: str) -> bool:
        """Check if a file path matches any allowlist pattern."""
        p = PurePosixPath(path).as_posix()
        return any(
            p == pat or p.startswith(pat + "/") or fnmatch(p, pat) 
            for pat in self.path_allowlist
        )

    def _is_placeholder(self, value: str) -> bool:
        """Check if a value is a known placeholder or dummy."""
        low = value.lower()
        return low in self.PLACEHOLDER_EXACT or (value.startswith("${") and value.endswith("}"))

    @staticmethod
    def _sha256(value: str) -> str:
        """Compute SHA-256 hash of a string."""
        return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()

    @staticmethod
    def _mask(value: str) -> str:
        """Mask a secret value for safe display."""
        return f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "*" * len(value)