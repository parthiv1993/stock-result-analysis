from pathlib import Path
from datetime import datetime, timezone
import csv
import requests

BASE = Path(__file__).resolve().parents[1]
META_DIR = BASE / "data" / "metadata"
META_DIR.mkdir(parents=True, exist_ok=True)

BSE_RESULTS_URL = "https://www.bseindia.com/corporates/Comp_Resultsnew.aspx"

def write_run_log(status: str, notes: str):
    file_path = META_DIR / "runs.csv"
    exists = file_path.exists()
    with file_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["run_utc", "status", "notes"])
        writer.writerow([datetime.now(timezone.utc).isoformat(), status, notes])

def fetch_bse_page():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.bseindia.com/",
    }
    r = requests.get(BSE_RESULTS_URL, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text

def write_placeholder_csv():
    out = META_DIR / "bse_results.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["company_name", "code", "result_link"])
    return out

def main():
    html = fetch_bse_page()
    out = write_placeholder_csv()
    write_run_log("ok", f"fetched_bse_results_page bytes={len(html)} csv={out.name}")
    print(f"Created {out}")

if __name__ == "__main__":
    main()