from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import csv
import requests
import re

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

def save_html(html: str):
    out = META_DIR / "bse_results_page.html"
    out.write_text(html, encoding="utf-8")
    return out

def make_result_link(code: str) -> str:
    return f"https://www.bseindia.com/stock-share-price/stockreach_financials.html?scripcode={code}"

def extract_result_announcements(html: str):
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)

    rows = []
    seen = set()

    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue

        looks_like_result = any(
            key in line.lower()
            for key in [
                "financial result",
                "audited financial result",
                "unaudited financial result",
                "quarter and year ended",
                "quarter ended",
                "year ended",
                "outcome of the board meeting",
            ]
        )

        if not looks_like_result:
            continue

        m = re.match(r"^(.*?)\s*-\s*(\d{6})\s*-\s*(.*)$", line)
        if not m:
            continue

        company_name = m.group(1).strip()
        code = m.group(2).strip()
        headline = m.group(3).strip()

        result_link = make_result_link(code)

        key = (company_name, code, headline)
        if key in seen:
            continue
        seen.add(key)

        rows.append({
            "company_name": company_name,
            "code": code,
            "result_link": result_link,
        })

    return rows

def write_csv(rows):
    out = META_DIR / "bse_results.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["company_name", "code", "result_link"])
        writer.writeheader()
        writer.writerows(rows)
    return out

def main():
    html = fetch_bse_page()
    html_file = save_html(html)
    rows = extract_result_announcements(html)
    csv_file = write_csv(rows)

    write_run_log(
        "ok",
        f"fetched_bse_results_page bytes={len(html)} html={html_file.name} csv={csv_file.name} rows={len(rows)}"
    )

    print(f"Saved {html_file}")
    print(f"Saved {csv_file} with {len(rows)} rows")

if __name__ == "__main__":
    main()