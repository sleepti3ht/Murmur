
<div align="center">

# 🌑 Murmur

[![python](https://img.shields.io/badge/Python-3.12%2B-27272a?style=flat&logo=python&logoColor=white)](https://python.org)
[![status](https://img.shields.io/badge/status-v1.1.0-27272a?style=flat)](https://github.com/sleepti3ht/Murmur/releases)
[![security](https://img.shields.io/badge/security-zero--knowledge-27272a?style=flat)](#)
[![license](https://img.shields.io/badge/license-MIT-27272a?style=flat)](LICENSE)

</div>

> ⚡ **Local-first, Zero-Knowledge secret scanner for Git.**  
> Murmur intercepts staged changes before a commit is created, detects credentials, and reports *only* SHA-256 hashes and masked strings. No raw secrets are logged, stored, or transmitted.

---

## 📦 Core Capabilities

### 🔍 Detection Pipeline
- **Pre-commit focused** — Scans staged changes via `git diff --cached`, not the entire repository.
- **Post-commit capable** — Compares `HEAD~1..HEAD` for local audit workflows.
- **Added-lines only** — Parses diff hunks to evaluate only newly introduced content.
- **Binary & Ignore filtering** — Skips binary files (`git diff --numstat`) and `.gitignore`-matched paths (even if force-staged).
- **Provider-aware rules** — Native patterns for AWS, GitHub, Slack, Google API keys, private keys, and generic `key = value` secrets.
- **Allowlist support** — Suppresses known noisy paths and selected benign SHA-256 hashes.

### 🛡️ Zero-Knowledge Security Model
- **No raw secrets in output** — Findings contain *only*: file path, line number, rule ID, severity, masked secret, and SHA-256 hash.
- **No active validation** — Murmur never sends detected tokens to external APIs or networks.
- **Default dry-run** — `DRY_RUN=1` by default. Findings are reported without blocking the developer workflow.
- **Fail-open resilience** — Adapter errors do not break the normal Git workflow in the MVP.

### ⚡ Developer Experience
- **Lightweight** — Pure Python + Pydantic. No Docker or heavy daemon required.
- **Millisecond feedback** — Optimized for minimal overhead during normal commits.
- **Modular architecture** — Detector logic is strictly decoupled from Git adapters, ready for future GitHub Events, Search API, or GitHub App integrations.

---

## 💡 Why This Matters

Most secret leaks happen *before* code review, CI, or push. A developer stages a file, commits it, and only later realizes a real API key was included.

Existing approaches often fail at the local level:
- **Remote/CI scanning** detects the secret *after* it exists in history.
- **Naive regex scripts** produce noisy alerts and leak raw secrets into terminal logs.
- **Monolithic scanners** mix Git, HTTP, alerting, and detection logic, making extension difficult.

**Murmur is designed as a local foolproof layer:**
1. It runs *before* the commit is created.
2. It only sees what is *about to be* committed.
3. It never stores or transmits raw secrets.

> **Note:** A local hook is a prevention layer, not a hard security boundary. It can be bypassed with `git commit --no-verify`. For mandatory enforcement, Murmur is designed to scale into a server-side GitHub App or CI-integrated scanner.

---

## 🔄 How It Works

```mermaid
graph TD
%% --- Grey UI Space Aesthetic Styles ---
classDef source fill:#27272a,stroke:#3f3f46,color:#e4e4e7,stroke-width:1px;
classDef core fill:#18181b,stroke:#27272a,color:#e4e4e7,stroke-width:1px;
classDef security fill:#3f3f46,stroke:#52525b,color:#e4e4e7,stroke-width:1px;
classDef output fill:#09090b,stroke:#27272a,color:#e4e4e7,stroke-width:1px;

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
    I[Console / SQLite report]:::output
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
│   ├── history.py           # Scan run history CLI
│   ├── adapters/            # base.py, git_hook.py
│   ├── core/                # models.py, detector.py
│   ├── alerting/            # console.py
│   └── storage/             # sqlite.py
├── tools/                   # make_test_repo.py, murmur_tray.py
├── tests/                   # test_detector.py
├── allowlist.txt.example
├── pyproject.toml
└── README.md
```

**Layering Philosophy:**  
The detector (`core/`) knows nothing about its input source. Whether data comes from a local Git hook today or a public GitHub Events stream tomorrow, the detection, hashing, and masking logic remains identical.

---

## 🚀 Setup

### 1. Prerequisites
- Python 3.12+
- Git
- A local virtual environment (No Docker required)

### 2. Installation
```bash
git clone https://github.com/sleepti3ht/Murmur.git
cd Murmur
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate

pip install -e .
```

### 3. Manual Execution
From the root of any target repository:
```bash
# Report mode (default)
PYTHONPATH=/absolute/path/to/Murmur DRY_RUN=1 python -m murmur.main "$PWD"

# Blocking mode
PYTHONPATH=/absolute/path/to/Murmur DRY_RUN=0 python -m murmur.main "$PWD"
```

### 4. Global Pre-commit Hook (Workstation-wide)
Apply Murmur to **all** repositories on your machine with a single configuration point:

```bash
# 1. Create shared hooks directory
mkdir -p ~/.githooks

# 2. Write the hook script (Linux/macOS)
cat > ~/.githooks/pre-commit << 'EOF'
#!/bin/sh
export PYTHONPATH="/absolute/path/to/Murmur"
export DRY_RUN="${MURMUR_DRY_RUN:-1}"
exec "/absolute/path/to/Murmur/.venv/bin/python" -m murmur.main
EOF
chmod +x ~/.githooks/pre-commit

# 3. Enable globally
git config --global core.hooksPath ~/.githooks
```
*(For Windows PowerShell, use the `Set-Content` method with UTF-8 no-BOM and LF line endings to ensure `sh` parses the shebang correctly).*

---

## ⚙️ Configuration

### Environment Variables
| Variable | Default | Description |
| :--- | :---: | :--- |
| `DRY_RUN` | `1` | `1`: Report only (exit `0`). `0`: Block commit on findings (exit `1`). |

### Allowlist
Murmur reads `allowlist.txt` from the current working directory.
```bash
cp allowlist.txt.example allowlist.txt
```
**Example `allowlist.txt`:**
```text
# Path-based (supports glob)
tests/fixtures/*
docs/examples/*.env.sample

# Hash-based (SHA-256 of the exact secret string)
# 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
```
> **Security Note:** SHA-256 is not encryption. Low-entropy secrets can be brute-forced from their hash. Prefer path-based allowlists for shared repositories.

---

## 🧪 Testing

```bash
pip install pytest
pytest -q
```

**Manual Verification:**
```bash
mkdir -p /tmp/murmur-test && cd /tmp/murmur-test
git init && git config user.email "test@local" && git config user.name "Test"
echo 'aws_key = "AKIAIOSFODNN7EXAMPLE"' > leak.py
git add leak.py

PYTHONPATH=/path/to/Murmur DRY_RUN=0 python -m murmur.main "$PWD"
echo $? # Expected: 1 (blocked)
```

---

## 🛡️ Security Guarantees

1. **Never log raw secrets** — Only masked values (`AKIA...MPLE`) are printed.
2. **Never store raw secrets** — SQLite history (`~/.murmur/findings.db`) stores only hashes and metadata.
3. **Never validate actively** — No HTTP requests are made using detected tokens.
4. **Separation of concerns** — The core detector is entirely decoupled from Git or network transports.

---

## ⚠️ Known Limitations

- **Bypassable locally:** `git commit --no-verify` skips the hook. Hard enforcement requires server-side push protection or CI.
- **Staged changes only:** Does not scan full repository history by default (answers *"Is this commit introducing a secret?"*, not *"Does this repo contain secrets?"*).
- **Regex boundaries:** Pattern matching is not semantic analysis. False positives may occur in test fixtures, lock files, or minified JS. Future iterations will introduce entropy scoring and context-aware rules.
- **Encoding edge cases:** Falls back to `latin-1` if UTF-8 decoding fails, preserving byte alignment but potentially missing exotic encodings (UTF-16/32).

---

<div align="center">
<br/>
<sub>Built with precision for local-first developer security.</sub>
<br/><br/>
<a href="https://github.com/sleepti3ht/Murmur/stargazers">
  <img src="https://img.shields.io/github/stars/sleepti3ht/Murmur?style=flat&color=27272a" alt="Stars" />
</a>
</div>

## License

MIT

