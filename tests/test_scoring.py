# tests/test_scoring.py
from murmur.core.entropy import shannon_entropy
from murmur.core.scoring import compute_confidence, is_placeholder


def test_shannon_entropy_empty():
    assert shannon_entropy("") == 0.0


def test_shannon_entropy_repetitive():
    # Low entropy for repetitive strings
    assert shannon_entropy("aaaa") < 1.0


def test_shannon_entropy_random():
    # High entropy for random-looking strings
    assert shannon_entropy("aB3$xK9#mP2@qL5!") > 3.5


def test_is_placeholder_env_var():
    assert is_placeholder("${API_KEY}") is True


def test_is_placeholder_angle_bracket():
    assert is_placeholder("<your_token>") is True


def test_is_placeholder_common_word():
    assert is_placeholder("changeme") is True


def test_is_placeholder_real_secret():
    assert is_placeholder("AKIAIOSFODNN7EXAMPLE") is False


def test_compute_confidence_aws_key():
    assert compute_confidence("aws.access_key_id", "AKIAIOSFODNN7EXAMPLE") == "high"


def test_compute_confidence_placeholder():
    assert compute_confidence("generic.secret", "changeme") == "noise"


def test_compute_confidence_high_entropy():
    secret = "aB3$xK9#mP2@qL5!vN8@"
    assert compute_confidence("generic.secret", secret) == "high"


def test_compute_confidence_low_entropy():
    assert compute_confidence("generic.secret", "password123") == "low"