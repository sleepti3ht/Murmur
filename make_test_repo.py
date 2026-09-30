# make_test_repo.py — creates a disposable repo with synthetic secrets.
import subprocess
import sys
from pathlib import Path

target = Path(sys.argv[1] if len(sys.argv) > 1 else "murmur-test").resolve()
target.mkdir(parents=True, exist_ok=True)

(target / "app").mkdir(exist_ok=True)
(target / "app" / "config.py").write_text(
    'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'
    'GITHUB_TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"\n'
    'api_key = "murmur_test_1234567890"\n'
    'SLACK_TOKEN = "xoxb-1234567890-abcdef"\n'
    'PRIVATE_KEY = "-----BEGIN RSA PRIVATE KEY-----"\n',
    encoding="utf-8",
)
(target / ".gitignore").write_text("ignored.env\n", encoding="utf-8")
(target / "ignored.env").write_text(
    'api_key = "murmur_ignored_secret_1234567890"\n', encoding="utf-8"
)
(target / "binary.bin").write_bytes(bytes(range(256)))

def git(*args: str) -> None:
    subprocess.run(["git", "-C", str(target), *args], check=True)

git("init")
git("config", "user.email", "test@test.local")
git("config", "user.name", "Murmur Test")
git("add", ".")
git("add", "-f", "ignored.env")  # stages an ignored file on purpose
print(f"Test repo ready: {target}")