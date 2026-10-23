# murmur/core/entropy.py
"""
Shannon entropy calculation for candidate secrets.

Higher entropy usually indicates more random-looking strings,
which are more likely to be actual secrets rather than placeholders
or common words.

Reference: https://en.wikipedia.org/wiki/Entropy_(information_theory)
"""
import math
from collections import Counter


def shannon_entropy(value: str) -> float:
    """
    Calculate Shannon entropy of a string.

    Args:
        value: Input string to analyze.

    Returns:
        Entropy value in bits per character.
        - 0.0 for empty strings or single-character strings.
        - ~1.0-2.0 for repetitive patterns (e.g., "aaaa").
        - ~3.0-4.0 for common words (e.g., "password").
        - ~4.5-6.0 for random-looking tokens (e.g., API keys).
    """
    if not value:
        return 0.0

    length = len(value)
    if length == 1:
        return 0.0

    frequencies = Counter(value)
    entropy = 0.0

    for count in frequencies.values():
        probability = count / length
        entropy -= probability * math.log2(probability)

    return entropy
