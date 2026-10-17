# murmur/alerting/console.py
"""
Console alerter for Murmur findings.
Uses ASCII markers instead of emojis for cross-platform compatibility
(Windows cp1251/cp866, CI/CD logs, etc.).
"""
from murmur.core.models import DetectionResult


class ConsoleAlerter:
    def notify(self, findings: list[dict]) -> None:
        if not findings:
            return
            
        print("\n[MURMUR] Potential secrets detected:")
        for f in findings:
            r = DetectionResult.model_validate(f)
            
            # ASCII markers for confidence levels
            confidence_marker = {
                "high": "[!]",
                "medium": "[*]",
                "low": "[.]",
            }.get(r.confidence, "[ ]")
            commit_part = f" | Commit: {r.commit_sha[:8]}" if r.commit_sha else ""
            print(
                f"  {confidence_marker} {r.file}:{r.line_number} | "
                f"Rule: {r.rule_id} | Confidence: {r.confidence.upper()} | "
                f"Mask: {r.masked_secret} | SHA256: {r.hashed_secret[:12]}...{commit_part}"
            )
