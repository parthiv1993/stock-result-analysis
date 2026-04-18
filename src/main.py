import csv
import os
from datetime import datetime, timezone
from pathlib import Path

from gdrive import upload_text_content

BASE = Path(__file__).resolve().parents[1]
META_DIR = BASE / "data" / "metadata"
META_DIR.mkdir(parents=True, exist_ok=True)

def write_run_log(status: str, notes: str):
    file_path = META_DIR / "runs.csv"
    exists = file_path.exists()
    with file_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["run_utc", "status", "notes"])
        writer.writerow([datetime.now(timezone.utc).isoformat(), status, notes])

def main():
    folder_id = os.environ.get("GDRIVE_FOLDER_ID")
    if not folder_id:
        write_run_log("error", "missing GDRIVE_FOLDER_ID")
        raise RuntimeError("Missing GDRIVE_FOLDER_ID")

    content = f"GitHub Actions Google Drive test at {datetime.now(timezone.utc).isoformat()}\n"
    uploaded = upload_text_content("gdrive-test.txt", content, folder_id)
    note = f"uploaded to gdrive file_id={uploaded['id']} name={uploaded['name']}"
    write_run_log("ok", note)
    print(note)

if __name__ == "__main__":
    main()