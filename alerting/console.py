from murmur.core.models import DetectionResult

class ConsoleAlerter:
    def notify(self, findings: list[dict]) -> None:
        if not findings: return
        print("\n[MURMUR] Potential secrets detected:")
        for f in findings:
            r = DetectionResult.model_validate(f)
            print(f"  - {r.file}:{r.line_number} | Rule: {r.rule_id} | Mask: {r.masked_secret} | SHA256: {r.hashed_secret[:12]}...")