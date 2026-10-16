# tools/murmur_tray.py
import sqlite3
import time

import pystray
from plyer import notification

from murmur.storage.sqlite import DB_PATH


def fetch_new(last_id: int) -> list[sqlite3.Row]:
    if not DB_PATH.exists():
        return []
    # Read-only connection: never blocks the hook's writes.
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row
        return con.execute(
            "SELECT * FROM findings WHERE id > ? ORDER BY id", (last_id,)
        ).fetchall()


def poll(icon: pystray.Icon, cursor: dict) -> None:
    while icon.visible:
        for row in fetch_new(cursor["id"]):
            notification.notify(
                title=f"Murmur: commit {row['action']}",
                message=f"{row['rule_id']} in {row['file']}:{row['line_number']}",
                timeout=5,
            )
            cursor["id"] = row["id"]
        time.sleep(3)
