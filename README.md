# 🎯 Murmur

> **Local-first secret scanner for Git repositories.** Murmur inspects staged changes before a commit is created, detects likely API keys, tokens, private keys, and generic secrets, and reports only masked values plus SHA-256 hashes. No raw secrets are logged, stored, or sent anywhere in the MVP.

![python](https://img.shields.io/badge/Python-3.12%2B-blue)
![status](https://img.shields.io/badge/status-MVP-yellow)
![security](https://img.shields.io/badge/security-zero--knowledge-informational)
![license](https://img.shields.io/badge/license-MIT-green)

---

## ✨ Features

### Detection Pipeline

- **Pre-commit focused** — scans staged changes using `git diff --cached`, not the whole repository
- **Post-commit capable** — can compare `HEAD~1..HEAD` for local audit workflows
- **Added-lines only** — parses diff hunks and checks only newly added content
- **Binary filtering** — skips binary files detected via `git diff --numstat`
- **Best-effort ignore filtering** — excludes files matched by `.gitignore`, including force-staged paths where practical
- **Provider-aware rules** — includes patterns for AWS, GitHub, Slack, Google API keys, private keys, and generic `key = value` secrets
- **Allowlist support** — suppresses known noisy paths and selected benign hashes

### Security Model

- **Zero-Knowledge output** — findings contain only:
  - file path
  - line number
  - rule ID
  - severity
  - masked secret
  - SHA-256 hash
- **No raw secrets in logs** — the scanner never prints the full matched secret
- **No active validation** — Murmur does not send found tokens to external APIs
- **No network calls in MVP** — local Git inspection only
- **Default dry-run** — `DRY_RUN=1` by default, so findings are reported without blocking commits
- **Fail-open local hook** — adapter errors do not break normal Git workflow in the MVP

### Developer Experience

- **Lightweight** — Python + Pydantic, no database required for MVP
- **No Docker required** — runs directly in a local virtual environment
- **Fast feedback** — intended for millisecond-scale overhead on normal commits
- **Simple integration** — works as a manual `pre-commit` hook or inside a Python environment
- **Test-friendly** — detector logic is separated from Git adapters

---

## 💡 Why This Matters

Most secret leaks happen before code review, before CI, and before the repository is pushed to GitHub. A developer stages a file, commits it, and only later realizes that a real API key was included.

Existing approaches often have one of these problems:

- **Remote scanning** — detects the secret after it has already been pushed
- **CI scanning** — detects it after the commit exists in history
- **Naive regex scripts** — produce noisy alerts and may leak raw secrets into logs
- **Monolithic scanners** — mix Git, HTTP, alerting, and detection logic, making future extension difficult

**Murmur is designed as a local foolproof layer:**

- It runs before the commit is created.
- It only sees what is about to be committed.
- It never stores or transmits raw secrets.
- It can be extended later with external adapters without rewriting the core detector.

**Important:** a local hook is not a mandatory security boundary. It can be bypassed with `git commit --no-verify`. For stronger protection, Murmur is intended to grow into a server-side GitHub App or CI-integrated scanner later.

---

## 🎯 Who Is This For?

**Independent developers and small teams who want local-first secret hygiene.**

You should use Murmur if you want to:

- catch accidental secrets before committing
- keep raw secrets out of local logs
- avoid sending credentials to third-party scanners
- build a modular scanner that can later support GitHub Events, Search API, or GitHub Apps
- protect your own workstation without running a daemon or Docker container

Murmur is not a replacement for:

- GitHub Secret Scanning
- server-side push protection
- secret rotation
- incident response
- formal vulnerability disclosure

It is a prevention layer.

---

## 🔄 How It Works

```mermaid
graph TD
%% --- Styles ---
classDef source fill:#2d3748,stroke:#4a5568,color:#fff,stroke-width:2px;
classDef core fill:#4c51bf,stroke:#434190,color:#fff,stroke-width:2px;
classDef security fill:#ed8936,stroke:#dd6b20,color:#fff;
classDef output fill:#38b2ac,stroke:#319795,color:#fff;

subgraph "1. Local Git Source"
    A[Staged changes<br/>git diff --cached]:::source
    B[Binary filter<br/>git diff --numstat]:::source
    C[Ignore filter<br/>git check-ignore]:::source
end

subgraph "2. Core Engine"
    D[Diff parser<br/>file / line / content]:::core
    E[SecretDetector<br/>regex rules]:::core
    F[Allowlist<br/>paths / hashes]:::security
end

subgraph "3. Zero-Knowledge Output"
    G[SHA-256 hash]:::output
    H[Masked secret<br/>first 4 ... last 4]:::output
    I[Console report]:::output
end

A --> D
B --> D
C --> D
D --> E
E --> F
F --> G
F --> H
G --> I
H --> I
```

---

## 📁 Project Structure

```text
murmur/
├── murmur/
│   ├── __init__.py
│   ├── main.py
│   ├── history.py
│   ├── adapters/   (base.py, git_hook.py)
│   ├── core/       (models.py, detector.py)
│   ├── alerting/   (console.py)
│   └── storage/    (sqlite.py)
├── tools/          (make_test_repo.py, murmur_tray.py)
├── tests/          (test_detector.py)
├── allowlist.txt.example
├── pyproject.toml
└── README.md
```

### Layering

- `adapters/` — sources of changes: local Git now, GitHub Events / Search API / GitHub Apps later
- `core/` — detection logic, models, hashing, masking, allowlists
- `alerting/` — output channels: console now, Telegram / SQLite / webhook notifications later

This separation is intentional. The detector should not know whether the input came from a local Git hook or a public GitHub event.

---

## 🚀 Setup

### 1. Prerequisites

- Python 3.12+
- Git
- A local virtual environment

No Docker is required.

### 2. Install Murmur

Clone the repository:

```bash
git clone https://github.com/yourusername/murmur.git
cd murmur
```

Create and activate a virtual environment:

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install pydantic
```

Optional editable install:

```bash
pip install -e .
```

### 3. Run Manually

From the root of a target repository:

```bash
PYTHONPATH=/absolute/path/to/murmur DRY_RUN=1 python -m murmur.main "$PWD"
```

Example:

```bash
cd /path/to/my-project
PYTHONPATH=/path/to/murmur DRY_RUN=1 python -m murmur.main "$PWD"
```

Default behavior:

- `DRY_RUN=1`
- findings are printed
- exit code is `0`
- commit is not blocked

Blocking mode:

```bash
PYTHONPATH=/path/to/murmur DRY_RUN=0 python -m murmur.main "$PWD"
```

In blocking mode:

- findings are printed
- exit code is `1`
- Git pre-commit hook fails

### 4. Install as a Local `pre-commit` Hook

In the target repository, run:

```bash
MURMUR_HOME=/absolute/path/to/murmur

cat > .git/hooks/pre-commit <<EOF
#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${MURMUR_HOME}:${PYTHONPATH:-}"
export DRY_RUN="${DRY_RUN:-1}"

python -m murmur.main "\$PWD"
EOF

chmod +x .git/hooks/pre-commit
```

Replace `/absolute/path/to/murmur` with the real path to your Murmur checkout.

Test it:

```bash
git add some_file.py
git commit -m "test: murmur hook"
```

If a fake secret is staged and `DRY_RUN=0`, the commit should be blocked.

### 5. Optional: `pre-commit` Framework

If you use the [`pre-commit`](https://pre-commit.com/) framework, you can add a local hook configuration:

```yaml
repos:
  - repo: local
    hooks:
      - id: murmur
        name: murmur secret scanner
        entry: python -m murmur.main
        language: system
        stages: [pre-commit]
        pass_filenames: false
```

This assumes Murmur is importable from the environment used by `pre-commit`.

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|---|---:|---|
| `DRY_RUN` | `1` | If `1`, report findings but do not block. If `0`, return exit code `1` on findings. |

Allowed false-like values for disabling dry-run:

```text
0
false
no
off
```

### Allowlist

Murmur reads `allowlist.txt` from the current working directory.

Recommended usage:

```bash
cp allowlist.txt.example allowlist.txt
```

Example:

```text
# Path-based allowlist
tests/fixtures/*
docs/examples/*.env.sample
services/legacy/config.test.py

# Optional hash-based allowlist
# Only use this for known benign high-entropy values.
# Do not commit hashes of weak production secrets.
# Example:
# 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
```

> **Security note:** SHA-256 is not encryption. If a secret has low entropy, its hash can be brute-forced. Prefer path-based allowlists for shared repositories. If hash allowlists become important, migrate to salted hashes or HMAC with a local secret key.

---

## 🧪 Testing

Run unit tests:

```bash
pip install pytest
pytest -q
```

Recommended manual test:

```bash
mkdir -p /tmp/murmur-test
cd /tmp/murmur-test
git init
git config user.email "test@test.local"
git config user.name "Test User"

cat > fake_secret.py <<'EOF'
aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"
EOF

git add fake_secret.py

PYTHONPATH=/absolute/path/to/murmur DRY_RUN=0 python -m murmur.main "$PWD"
echo $?
```

Expected result:

```text
exit code = 1
```

And output should contain only masked/hash data, never the full raw secret.

---

## 🛡️ Security Guarantees

Murmur MVP is designed around these rules:

1. **Never log raw secrets**
   - Only masked values are printed.
   - Example: `AKIA...MPLE`

2. **Never store raw secrets**
   - MVP keeps no persistent secret storage.

3. **Never validate secrets actively**
   - No HTTP requests are made using detected tokens.
   - No calls to AWS, GitHub, Slack, or other providers.

4. **Default to dry-run**
   - `DRY_RUN=1` is the default.
   - Blocking must be explicit.

5. **Separate detection from transport**
   - The core detector does not depend on Git or GitHub APIs.
   - Future adapters can reuse the same detection logic.

---

## ⚠️ Known Limitations

### Local hooks are not mandatory

A developer can bypass the hook:

```bash
git commit --no-verify
```

This is expected. Local hooks are a usability and prevention layer, not a hard security boundary.

For hard enforcement, use:

- server-side push protection
- GitHub App webhook validation
- CI checks
- signed commit policies
- organizational Git hooks

### MVP scans staged changes only

Murmur does not scan the full repository history by default.

It answers this question:

> “Is this commit about to introduce a likely secret?”

It does not answer:

> “Does this repository already contain secrets in old commits?”

Full-history scanning is a separate mode and should be added carefully.

### Regex detection has false positives and false negatives

Murmur uses pattern matching. It is not semantic analysis.

Common false-positive sources:

- test fixtures
- documentation examples
- placeholder values
- generated lock files
- minified JavaScript
- base64 blobs
- random non-secret identifiers

Common false-negative sources:

- obfuscated secrets
- split strings
- encrypted configuration
- unusual encodings
- secrets embedded in binary-like text files

Future improvements should include:

- entropy scoring
- context-aware rules
- provider-specific validators that do not perform active network checks
- allowlist management
- confidence thresholds

### Encoding edge cases

Git diffs may contain non-UTF-8 data.

Current behavior:

- attempt UTF-8 decoding
- fallback to Latin-1 to preserve byte alignment

This avoids crashes, but exotic encodings such as UTF-16, UTF-32, or legacy codepages may not be detected reliably.

### Race conditions

The Git adapter executes multiple Git
