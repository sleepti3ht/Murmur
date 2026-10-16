# murmur/alerting/console.py
from murmur.core.models import DetectionResult


class ConsoleAlerter:
    def notify(self, findings: list[dict]) -> None:
        if not findings:
            return
        print("\n[MURMUR] Potential secrets detected:")
        for f in findings:
            r = DetectionResult.model_validate(f)
            confidence_marker = {
                "high": "🔴",
                "medium": "🟡",
                "low": "",
            }.get(r.confidence, "⚪")
            print(
                f"  {confidence_marker} {r.file}:{r.line_number} | "
                f"Rule: {r.rule_id} | Confidence: {r.confidence} | "
                f"Mask: {r.masked_secret} | SHA256: {r.hashed_secret[:12]}..."
            )