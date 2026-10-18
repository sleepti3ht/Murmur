
<div align="center">

# 🌑 Murmur

[![python](https://img.shields.io/badge/Python-3.12%2B-18181b?style=flat&logo=python&logoColor=a855f7)](https://python.org)
[![rust](https://img.shields.io/badge/Rust-Tauri%202-18181b?style=flat&logo=rust&logoColor=a855f7)](https://tauri.app)
[![version](https://img.shields.io/badge/v1.10.0-18181b?style=flat)](https://github.com/sleepti3ht/Murmur/releases)
[![security](https://img.shields.io/badge/zero--knowledge-18181b?style=flat&color=a855f7)](#)
[![license](https://img.shields.io/badge/MIT-18181b?style=flat)](LICENSE)

</div>

<div align="center">

### *Local-first, zero-knowledge secret scanner for Git.*

Murmur intercepts staged changes before a commit is created, before a push is sent, and before a baseline drifts. Findings are reported as **SHA-256 hashes and masked strings only** — raw secrets never touch the disk, the terminal, or the network.

[Installation](#-installation) · [Dashboard](#-dashboard) · [Configuration](#-configuration) · [Architecture](#-architecture)

</div>

---

## 🎯 Why Murmur

Most secret leaks happen *before* code review, CI, or push. A developer stages a file, commits it, and only later realises a real API key was included. Existing approaches fail at the local level:

| Approach | Failure mode |
| :--- | :--- |
| Remote / CI scanning | Detects secrets *after* they are in history |
| Naive regex scripts | Noisy alerts, raw secrets leak into terminal logs |
| Monolithic scanners | Git, HTTP, alerting and detection mixed — extension is hard |

**Murmur closes the loop locally** with a layered defence model:

1. **Pre-commit hook** — intercepts staged changes before the commit exists.
2. **Pre-push hook** — catches bypasses (`--no-verify`, `commit --amend`) before the push leaves the machine.
3. **Baseline mode** — suppresses accepted technical debt, alerts only on *new* secrets.
4. **Custom YAML rules** — extend detection to proprietary token formats.
5. **Desktop dashboard** — observe findings, scans and logs across all repositories on the workstation.

---

## ✨ Features

```
┌─────────────────────────────────────────────────────────────────────┐
│  Detection                 UX                      Observability    │
├─────────────────────────────────────────────────────────────────────┤
│  • Pre-commit hook         • Tauri 2 desktop app   • Findings tab  │
│  • Pre-push guard          • Purple dark/light UI  • Scans tab     │
│  • History audit           • System tray           • Logs tab      │
│  • External repo scan      • Rule playground       • SQLite WAL    │
│  • Entropy scoring         • Custom YAML rules     • Attribution   │
│  • Baseline suppression    • Portable exe bundle                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 🔍 Detection Pipeline
- **Staged-changes only** — parses `git diff --cached`, ignores untouched files.
- **Binary & `.gitignore` filtering** — skipped via `git diff --numstat` and `git check-ignore`.
- **Provider-aware rules** — AWS, GitHub, Slack, Google, private keys, generic `key = value`.
- **Entropy-based confidence** — Shannon entropy scoring eliminates noise from low-entropy test fixtures.
- **Allowlist** — path globs and exact SHA-256 hashes.

### 🛡️ Security Model
- **No raw secrets anywhere** — output contains only file, line, rule ID, masked secret and SHA-256.
- **No active validation** — Murmur never sends detected tokens to external APIs.
- **Fail-open resilience** — adapter errors never break the normal Git workflow.
- **Atomic writes** — custom rules and baseline files written via `tempfile + os.replace`.

### ⚡ Performance
- **Lightweight core** — pure Python + Pydantic, no Docker or daemon required for the hook.
- **Millisecond feedback** — typical pre-commit overhead is under 50 ms.
- **Portable desktop app** — Tauri 2 shell (~8 MB) + PyInstaller sidecar (~16 MB).

---

## 🖼️ Screenshots

<!-- PLACEHOLDER: Replace with real screenshots -->

| Dark theme | Light theme |
| :---: | :---: |
| ![dashboard-dark](docs/screenshots/dashboard-dark.png) | ![dashboard-light](docs/screenshots/dashboard-light.png) |

| Findings view | Custom Rules |
| :---: | :---: |
| ![findings](docs/screenshots/findings.png) | ![rules](docs/screenshots/rules.png) |

| Playground | Scans & Logs |
| :---: | :---: |
| ![playground](docs/screenshots/playground.png) | ![scans-logs](docs/screenshots/scans-logs.png) |

| Pre-commit block | System tray |
| :---: | :---: |
| ![pre-commit](docs/screenshots/pre-commit.png) | ![tray](docs/screenshots/tray.png) |

---

## 🏗️ Architecture

```mermaid
graph TD
classDef src fill:#18181b,stroke:#3f3f46,color:#e4e4e7,stroke-width:1px
classDef core fill:#27272a,stroke:#a855f7,color:#e4e4e7,stroke-width:1px
classDef storage fill:#3f3f46,stroke:#52525b,color:#e4e4e7,stroke-width:1px
classDef ui fill:#09090b,stroke:#a855f7,color:#e4e4e7,stroke-width:1px

subgraph "1. Git Events"
    A[pre-commit<br/>git diff --cached]:::src
    B[pre-push<br/>stdin ref specs]:::src
    C[history<br/>git log -p]:::src
end

subgraph "2. Detection Core"
    D[Diff parser<br/>+ attribution]:::core
    E[SecretDetector<br/>regex + entropy]:::core
    F[Allowlist<br/>+ Baseline]:::core
end

subgraph "3. Storage (SQLite WAL)"
    G[findings]:::storage
    H[runs]:::storage
    I[logs]:::storage
end

subgraph "4. Observability"
    J[Tauri 2 dashboard<br/>Vanilla JS]:::ui
    K[FastAPI sidecar]:::ui
    L[Console alert]:::ui
end

A --> D
B --> D
C --> D
D --> E
E --> F
F --> G
F --> H
F --> I
F --> L
G --> K
H --> K
I --> K
K --> J
```

**Layering principle:** the detector knows nothing about its input source. Whether data arrives from a local Git hook, a `git log` audit, or (in v2.0) a GitHub webhook, detection, hashing and masking remain identical.

---

## 📁 Project Structure

```text
Murmur/
├── murmur/                      # Core detection engine
│   ├── core/
│   │   ├── detector.py          # Regex + custom rule merging, fail-open
│   │   ├── models.py            # Pydantic ChangeLine, DetectionResult
│   │   ├── scoring.py           # Confidence classification
│   │   ├── entropy.py           # Shannon entropy
│   │   └── baseline.py          # Snapshot accepted debt
│   ├── adapters/
│   │   ├── base.py
│   │   ├── git_hook.py          # pre-commit
│   │   ├── git_push.py          # pre-push (stdin ref specs)
│   │   └── history.py           # git log -p parser
│   ├── alerting/                # Console output formatter
│   ├── storage/                 # SQLite (findings, runs, logs)
│   ├── external_scan.py         # Clone + scan arbitrary repos
│   ├── main.py                  # Hook entry point
│   └── baseline.py              # CLI for baseline management
├── dashboard/
│   ├── api.py                   # FastAPI backend
│   ├── src/                     # Vanilla JS + CSS frontend
│   └── Tauri/                   # Rust shell, tray, sidecar lifecycle
├── tools/
│   ├── install_hook.py          # Idempotent global hook installer
│   ├── generate_icons.py        # Tauri icon asset generator
│   └── make_test_repo.py        # Fixture repository builder
├── tests/
├── allowlist.txt
├── pyproject.toml
└── README.md
```

---

## 🚀 Installation

### 1. Prerequisites
- Python 3.12+
- Git
- Rust toolchain (only if building the desktop app from source)

### 2. Clone and install

```bash
git clone https://github.com/sleepti3ht/Murmur.git
cd Murmur
python -m venv .venv

# Windows
.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

pip install -e .
```

### 3. Install global Git hooks

One command — hooks apply to **every** repository on the machine.

```bash
python tools/install_hook.py
```

This creates `pre-commit` and `pre-push` scripts in `~/.githooks` and points `core.hooksPath` at that directory.

### 4. Environment variables (optional)

| Variable | Default | Description |
| :--- | :---: | :--- |
| `DRY_RUN` | `1` | `1` = report only, `0` = block on findings |
| `MURMUR_SKIP` | — | Set to `1` to intentionally bypass the pre-push guard |

---

## 🖥️ Dashboard

The desktop dashboard is a portable Windows bundle:

- **`murmur-dashboard.exe`** — Tauri 2 shell, system tray, single-instance enforcement.
- **`murmur-api/`** — PyInstaller sidecar spawned and reaped by the shell.

On first launch the shell spawns the API as a child process with `CREATE_NO_WINDOW` and kills the entire process tree (`taskkill /T /F`) on graceful exit — no orphan servers, no leaked port bindings.

### Tabs
| Tab | Purpose |
| :--- | :--- |
| **Findings** | All detected secrets with confidence, mask, commit SHA |
| **Custom Rules** | Manage user-defined YAML detection rules |
| **Playground** | Test arbitrary strings against active rules + one-off regex |
| **Scans** | Every hook invocation, including clean commits |
| **Logs** | Capped audit log (5,000-row retention) |

---

## ⚙️ Configuration

### Allowlist

Create `allowlist.txt` at the root of any repository:

```text
# Path-based (glob supported)
tests/fixtures/*
docs/examples/*.env.sample

# Hash-based (SHA-256 of the exact secret string)
9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
```

> ⚠️ **Security note:** SHA-256 is not encryption. Low-entropy secrets can be brute-forced from their hash. Prefer path-based allowlists for shared repositories.

### Custom rules

Create `~/.murmur/custom_rules.yaml`:

```yaml
rules:
  - id: vendor.internal_token
    pattern: "INT-[A-Za-z0-9]{32}"
    severity: high
    confidence: high    # optional: bypasses entropy scoring
    description: "Internal vendor token"
    active: true
```

Rules are validated on load — invalid regexes are skipped with a stderr warning so a single bad rule never breaks the hook.

### Baseline mode

Snapshot existing debt on legacy repositories:

```bash
# Snapshot current HEAD
python -m murmur.baseline create

# Inspect
python -m murmur.baseline show
```

Creates `.murmur-baseline.json` with SHA-256 hashes of accepted secrets. Subsequent scans suppress these hashes and alert only on newly introduced ones.

### History audit

One-shot scan of repository history with commit attribution:

```bash
python -m murmur.history_scan . --max-commits 50
```

---

## 🛡️ Security Guarantees

1. **Never log raw secrets** — only `AKIA...MPLE` style masks appear in output.
2. **Never store raw secrets** — the SQLite database holds hashes and metadata only.
3. **Never validate actively** — no outbound HTTP from the detection engine.
4. **Atomic writes** — `tempfile + os.replace` prevents torn YAML/JSON during concurrent hook invocations.
5. **Fail-open per rule** — a malformed custom rule is skipped, never crashes the hook.

---

## 🧪 Testing

```bash
pip install pytest
pytest -q
```

### Manual verification

```bash
mkdir -p /tmp/murmur-test && cd /tmp/murmur-test
git init
git config user.email "test@local" && git config user.name "Test"

echo 'aws_key = "AKIAIOSFODNN7EXAMPLE"' > leak.py
git add leak.py

PYTHONPATH=/path/to/Murmur DRY_RUN=0 python -m murmur.main "$PWD"
echo $?   # Expected: 1 (blocked)
```

---

## ⚠️ Known Limitations

- **Bypassable locally** — `git commit --no-verify` skips the pre-commit hook. The pre-push hook closes this gap for pushes from the same machine, but pushes from other machines (or the GitHub web UI) are not covered. Server-side enforcement is the v2.0 roadmap.
- **Staged changes only by default** — answers *"Is this commit introducing a secret?"*, not *"Does this repo contain secrets?"*. Use `python -m murmur.history_scan` for the latter.
- **Regex boundaries** — pattern matching is not semantic analysis. Entropy scoring mitigates most noise, but false positives can still appear in lockfiles or minified JS.
- **Encoding fallback** — falls back to `latin-1` when UTF-8 decoding fails, preserving byte alignment but potentially missing exotic encodings (UTF-16/32).

---

## 🗺️ Roadmap

- [x] **v1.0** — Pre-commit hook, core detector, allowlist.
- [x] **v1.5** — Tauri desktop dashboard with system tray.
- [x] **v1.8** — Custom YAML rules with fail-open validation.
- [x] **v1.9** — Pre-push guard, baseline mode, playground, history attribution.
- [x] **v1.10** — Portable bundle, scans tab, capped logs table.
- [ ] **v2.0** — GitHub App / webhook server for server-side push protection.
- [ ] **v2.1** — Slack / Teams / email alerting adapters.

---

## 🤝 Contributing

Issues and pull requests are welcome. Please keep the zero-knowledge guarantee intact: no code path should ever log, store or transmit a raw secret.

---

## License

MIT
