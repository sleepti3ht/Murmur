# tests/test_detector.py
import hashlib

from murmur.core.detector import SecretDetector

AWS_SECRET = "AKIAIOSFODNN7EXAMPLE"
GITHUB_TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def line(content: str, path: str = "app/config.py") -> list[dict]:
    return [{"file": path, "line_number": 1, "content": content}]


def test_detects_aws_access_key():
    findings = SecretDetector().analyze(line(f'aws_key = "{AWS_SECRET}"'))
    assert findings
    assert findings[0]["rule_id"] == "aws.access_key_id"
    assert findings[0]["masked_secret"] == "AKIA...MPLE"


def test_detects_github_token():
    findings = SecretDetector().analyze(line(f'token = "{GITHUB_TOKEN}"'))
    assert findings
    assert findings[0]["rule_id"] == "github.token"


def test_zero_knowledge_output():
    findings = SecretDetector().analyze(line(f'aws_key = "{AWS_SECRET}"'))
    blob = str(findings)
    assert AWS_SECRET not in blob
    assert GITHUB_TOKEN not in blob


def test_path_allowlist():
    detector = SecretDetector(allowlist=["app/config.py"])
    assert detector.analyze(line(f'aws_key = "{AWS_SECRET}"')) == []


def test_hash_allowlist():
    secret_hash = hashlib.sha256(AWS_SECRET.encode()).hexdigest()
    detector = SecretDetector(allowlist=[secret_hash])
    assert detector.analyze(line(f'aws_key = "{AWS_SECRET}"')) == []


def test_placeholder_unit():
    assert SecretDetector()._is_placeholder("changeme") is True
    assert SecretDetector()._is_placeholder(AWS_SECRET) is False
