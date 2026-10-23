# tools/install_hook.py
"""
Idempotent installer for global Murmur Git hooks (pre-commit + pre-push).

Writes LF-encoded hook scripts into ~/.githooks and points the global
core.hooksPath at that directory. Safe to re-run at any time.
"""
import os
import stat
import subprocess
import sys
from pathlib import Path

HOOK_TEMPLATE = """#!/bin/sh
# Murmur {mode} hook (managed by tools/install_hook.py)
if [ "$MURMUR_SKIP" = "1" ]; then
    exit 0
fi
export PYTHONPATH="{home}"
export DRY_RUN="${{MURMUR_DRY_RUN:-{dry_run}}}"
exec "{python}" -m murmur.main "$PWD" {mode_flag}
"""


def main() -> int:
    home = Path(__file__).resolve().parent.parent
    python = sys.executable
    hooks_dir = Path.home() / ".githooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    specs = [("pre-commit", ""), ("pre-push", "--mode=pre-push")]
    for name, flag in specs:
        body = HOOK_TEMPLATE.format(
            home=home.as_posix(),
            python=python,
            mode=name,
            mode_flag=flag,
            dry_run=os.getenv("MURMUR_DRY_RUN", "0"),
        )
        target = hooks_dir / name
        target.write_text(body, encoding="utf-8", newline="\n")
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"[MURMUR] Installed hook: {target}")

    subprocess.run(
        ["git", "config", "--global", "core.hooksPath", hooks_dir.as_posix()],
        check=True,
    )
    print(f"[MURMUR] core.hooksPath -> {hooks_dir}")
    print("[MURMUR] Done. Hooks now apply to every repository on this machine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
