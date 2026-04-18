from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from urllib.parse import urljoin
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

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def find_nearest_row_text(tag):
    node = tag
    for _ in range(8):
        if node is None:
            break
        text = clean_text(node.get_text(" ", strip=True))
        if text:
            code_match = re.search(r"\b(\d{6})\b", text)
            if code_match:
                return text
        node = node.parent
    return ""

def parse_result_links(html: str):
    soup = BeautifulSoup(html, "lxml")
    rows = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        href_lower = href.lower()

        if not any(token in href_lower for token in ["xbrl", "xbrldetails", "pdf", "attach"]):
            continue

        full_link = urljoin(BSE_RESULTS_URL, href)
        context_text = find_nearest_row_text(a)

        if not context_text:
            continue

        code_match = re.search(r"\b(\d{6})\b", context_text)
        if not code_match:
            continue

        code = code_match.group(1)

        company_match = re.search(r"\b\d{6}\b\s+(.*?)\s+(MQ|MC|JQ|JC|SQ|SC|DQ|DC|MH|JH|SH|DH|A|U)\b", context_text)
        if company_match:
            company_name = clean_text(company_match.group(1))
        else:
            parts = re.split(r"\b\d{6}\b", context_text, maxsplit=1)
            company_name = clean_text(parts[1]) if len(parts) > 1 else ""

            company_name = re.split(r"\b(MQ|MC|JQ|JC|SQ|SC|DQ|DC|MH|JH|SH|DH)\d{4}-\d{4}\b", company_name)[0]
            company_name = clean_text(company_name)

        if not company_name:
            continue

        key = (company_name, code, full_link)
        if key in seen:
            continue
        seen.add(key)

        rows.append({
            "company_name": company_name,
            "code": code,
            "result_link": full_link,
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
    rows = parse_result_links(html)
    csv_file = write_csv(rows)

    write_run_log(
        "ok",
        f"fetched_bse_results_page bytes={len(html)} html={html_file.name} csv={csv_file.name} rows={len(rows)}"
    )

    print(f"Saved {html_file}")
    print(f"Saved {csv_file} with {len(rows)} rows")

if __name__ == "__main__":
    main()