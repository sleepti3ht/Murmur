# tools/murmur_tray.py
"""
Murmur Tray Observer.
Monitors ~/.murmur/findings.db and shows native OS notifications on new findings.
"""
import os
import sqlite3
import sys
import threading
import time
from pathlib import Path

import pystray
from PIL import Image, ImageDraw
from plyer import notification

# Add project root to path to allow importing murmur modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from murmur.storage.sqlite import DB_PATH

LOCK_FILE = Path.home() / ".murmur" / "tray.lock"

def create_icon_image():
    """Generates a simple dark grey icon with an 'M'."""
    size = (64, 64)
    image = Image.new("RGBA", size, (39, 39, 42, 255)) # Zinc-800
    draw = ImageDraw.Draw(image)
    draw.text((16, 12), "M", fill=(228, 228, 231, 255), font_size=40) # Zinc-200
    return image

def is_already_running():
    """Prevents multiple tray instances."""
    if LOCK_FILE.exists():
        try:
            # Check if the PID in the lock file is still alive
            with open(LOCK_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0) # Raises ProcessLookupError if dead
            return True
        except (ProcessLookupError, ValueError):
            LOCK_FILE.unlink(missing_ok=True)

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    return False

def poll_db(icon: pystray.Icon):
    """Background thread that polls the DB for new blocked/reported events."""
    last_id = 0
    while icon.visible:
        if not DB_PATH.exists():
            time.sleep(2)
            continue

        try:
            # Read-only connection to avoid locking the git hook writer
            con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row

            # We only care about 'blocked' or 'reported' runs that have findings
            cursor = con.execute(
                "SELECT * FROM runs WHERE id > ? AND action IN ('blocked', 'reported') ORDER BY id ASC",
                (last_id,)
            )
            runs = cursor.fetchall()

            for run in runs:
                last_id = run['id']

                # Get the specific findings for this run to show in the toast
                # (Matching by repo and approximate time is a simple heuristic)
                findings_cursor = con.execute(
                    "SELECT rule_id, file FROM findings WHERE repo = ? ORDER BY id DESC LIMIT 3",
                    (run['repo'],)
                )
                findings = findings_cursor.fetchall()

                rules = ", ".join([f['rule_id'].split('.')[-1] for f in findings])
                repo_name = Path(run['repo']).name

                title = "🚨 Murmur: Secret Blocked" if run['action'] == 'blocked' else "⚠️ Murmur: Secret Reported"
                message = f"Repo: {repo_name}\nRules: {rules}\nAction: Commit {run['action']}"

                # Show native OS notification
                notification.notify(
                    title=title,
                    message=message,
                    timeout=5,
                )

            con.close()
        except sqlite3.OperationalError:
            pass # DB locked by hook, retry next cycle

        time.sleep(1.5) # Poll every 1.5 seconds

def on_exit(icon, item):
    """Cleanup and exit."""
    if LOCK_FILE.exists():
        LOCK_FILE.unlink(missing_ok=True)
    icon.stop()

def main():
    if is_already_running():
        print("[MURMUR TRAY] Another instance is already running.")
        return

    print("[MURMUR TRAY] Starting observer... (Check your system tray)")

    icon_image = create_icon_image()
    menu = pystray.Menu(
        pystray.MenuItem("Show History", lambda icon, item: print("History feature coming in v1.3")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", on_exit)
    )

    icon = pystray.Icon("murmur_tray", icon_image, "Murmur Guardian", menu)

    # Start polling in a daemon thread
    poll_thread = threading.Thread(target=poll_db, args=(icon,), daemon=True)
    poll_thread.start()

    # Run the tray main loop
    icon.run()

if __name__ == "__main__":
    main()
