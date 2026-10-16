# murmur/live.py
"""
Live stream of Murmur scan events.
Usage: python -m murmur.live
"""
import sys
import time
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".murmur" / "findings.db"

def get_db_connection():
    if not DB_PATH.exists():
        return None
    # Read-only connection to avoid locking the writer (the hook)
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

def stream_events():
    print("[MURMUR LIVE] Monitoring local git commits... (Ctrl+C to stop)\n")
    
    last_run_id = 0
    last_finding_id = 0

    while True:
        con = get_db_connection()
        if not con:
            time.sleep(2)
            continue
            
        con.row_factory = sqlite3.Row
        
        try:
            # 1. Stream Runs (to show that hook is alive, even on clean commits)
            cursor = con.execute(
                "SELECT * FROM runs WHERE id > ? ORDER BY id ASC", 
                (last_run_id,)
            )
            runs = cursor.fetchall()
            
            for run in runs:
                last_run_id = run['id']
                status_color = "\033[92m" if run['action'] == 'passed' else "\033[91m"
                reset_color = "\033[0m"
                
                print(f"{status_color}[{run['ts']}] {run['action'].upper()}{reset_color} | Repo: {run['repo']} | Files: {run['files_scanned']} | Time: {run['duration_ms']}ms")

            # 2. Stream Findings (only if secrets were detected)
            cursor = con.execute(
                "SELECT * FROM findings WHERE id > ? ORDER BY id ASC", 
                (last_finding_id,)
            )
            findings = cursor.fetchall()
            
            for f in findings:
                print(f"  \033[93m-> DETECTED: {f['rule_id']} in {f['file']}:{f['line_number']}\033[0m")
                print(f"     Mask: {f['masked']} | Hash: {f['hash'][:16]}...")
                last_finding_id = f['id']
                
        except sqlite3.OperationalError:
            # DB might be locked for a millisecond during write
            pass
        finally:
            con.close()
            
        time.sleep(1) # Polling interval

if __name__ == "__main__":
    try:
        stream_events()
    except KeyboardInterrupt:
        print("\n[MURMUR LIVE] Stopped.")
        sys.exit(0)