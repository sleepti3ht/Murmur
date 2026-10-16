# murmur/core/scoring.py
"""
Confidence scoring for secret detection findings.

Combines multiple signals to produce a confidence level:
- Rule specificity (provider-specific rules are higher confidence)
- Shannon entropy (higher entropy = more likely to be a real secret)
- String length (very short strings are less likely to be secrets)
- Placeholder detection (common dummy values are filtered out)

Confidence levels:
- "high": Provider-specific rule OR high entropy + sufficient length
- "medium": Generic rule with moderate entropy
- "low": Generic rule with low entropy (likely false positive)
- "noise": Placeholder or known benign pattern (should be filtered)
"""
from murmur.core.entropy import shannon_entropy

# Rules that are highly specific and rarely produce false positives
HIGH_CONFIDENCE_RULES = {
    "aws.access_key_id",
    "aws.secret_access_key",
    "github.token",
    "slack.token",
    "google.api_key",
    "private_key",
}

# Common placeholder patterns that should be classified as noise
PLACEHOLDER_PATTERNS = {
    "example",
    "changeme",
    "dummy",
    "placeholder",
    "your_",
    "your-",
    "test",
    "sample",
    "todo",
    "xxx",
    "insert_",
    "replace_",
}


def is_placeholder(value: str) -> bool:
    """
    Check if a value looks like a placeholder or dummy value.

    Args:
        value: The candidate secret string.

    Returns:
        True if the value appears to be a placeholder.
    """
    lowered = value.lower()

    # Environment variable syntax: ${VAR_NAME}
    if lowered.startswith("${") and lowered.endswith("}"):
        return True

    # Angle bracket syntax: <VAR_NAME>
    if lowered.startswith("<") and lowered.endswith(">"):
        return True

    # Check for common placeholder substrings
    return any(marker in lowered for marker in PLACEHOLDER_PATTERNS)


def compute_confidence(rule_id: str, secret: str) -> str:
    """
    Compute confidence level for a secret detection finding.

    Args:
        rule_id: The ID of the matched rule (e.g., "aws.access_key_id").
        secret: The extracted secret value.

    Returns:
        Confidence level: "high", "medium", "low", or "noise".
    """
    # Filter obvious placeholders
    if is_placeholder(secret):
        return "noise"

    # Provider-specific rules are high confidence by default
    if rule_id in HIGH_CONFIDENCE_RULES:
        return "high"

    # For generic rules, use entropy and length heuristics
    entropy = shannon_entropy(secret)
    length = len(secret)

    # High entropy + sufficient length = likely real secret
    if entropy >= 4.5 and length >= 20:
        return "high"

    # Moderate entropy + reasonable length = possible secret
    if entropy >= 3.8 and length >= 16:
        return "medium"

    # Low entropy or very short = likely false positive
    return "low"