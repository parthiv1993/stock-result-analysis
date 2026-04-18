from pathlib import Path
from datetime import datetime, timezone
import csv

BASE = Path(__file__).resolve().parents[1]
META_DIR = BASE / "data" / "metadata"
META_DIR.mkdir(parents=True, exist_ok=True)

def write_run_log():
    file_path = META_DIR / "runs.csv"
    exists = file_path.exists()
    with file_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["run_utc", "status", "notes"])
        writer.writerow([datetime.now(timezone.utc).isoformat(), "ok", "scaffold run completed"])

if __name__ == "__main__":
    write_run_log()
    print("Scaffold run complete")
