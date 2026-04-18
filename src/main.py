from pathlib import Path
from datetime import datetime, date
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import csv
import os
import re
import requests

BASE = Path(__file__).resolve().parents[1]
META_DIR = BASE / "data" / "metadata"
META_DIR.mkdir(parents=True, exist_ok=True)

SCREENER_BASE = "https://www.screener.in"


def write_run_log(status: str, notes: str):
    file_path = META_DIR / "runs.csv"
    exists = file_path.exists()
    with file_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["run_utc", "status", "notes"])
        writer.writerow([datetime.utcnow().isoformat() + "Z", status, notes])


def build_latest_results_url(d: date) -> str:
    return (
        f"{SCREENER_BASE}/results/latest/"
        f"?result_update_date__day={d.day}"
        f"&result_update_date__month={d.month}"
        f"&result_update_date__year={d.year}"
    )


def fetch_html(url: str, session: requests.Session) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": SCREENER_BASE,
    }
    r = session.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def extract_companies_from_latest(html: str):
    """
    From /results/latest/ page:
    - find all /company/... links
    - dedupe
    """
    soup = BeautifulSoup(html, "lxml")
    seen = set()
    companies = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("/company/"):
            continue

        full_url = urljoin(SCREENER_BASE, href.split("?")[0])
        name = a.get_text(" ", strip=True)

        key = full_url
        if key in seen:
            continue
        seen.add(key)

        if not name:
            continue

        companies.append(
            {
                "company_name": name,
                "screener_url": full_url,
            }
        )

    return companies


def extract_latest_pdf_from_company(html: str) -> str:
    """
    On a company page, look for the quarterly results section and
    try to find a link to the raw PDF.

    Screener's changelog: "Added links to raw PDFs in quarterly results" [web:431].
    Heuristic:
    - find headings containing 'Quarterly results'
    - search below them for <a> with 'pdf' in href or 'raw' in text
    """
    soup = BeautifulSoup(html, "lxml")
    text_re = re.compile(r"quarterly results", re.I)

    sections = []

    # 1) find headings that mention 'Quarterly results'
    for heading_tag in ["h2", "h3", "h4"]:
        for h in soup.find_all(heading_tag):
            if text_re.search(h.get_text(" ", strip=True) or ""):
                sections.append(h.parent)

    # fallback: consider entire page if section not found
    search_roots = sections or [soup]

    for root in search_roots:
        # priority: explicit "Raw PDF" or ".pdf" links
        for a in root.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(" ", strip=True).lower()

            if ".pdf" in href.lower():
                return urljoin(SCREENER_BASE, href)
            if "raw" in text and "pdf" in text:
                return urljoin(SCREENER_BASE, href)

    return ""


def write_results_csv(rows):
    out = META_DIR / "screener_results.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["company_name", "screener_url", "result_pdf_link"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return out


def main():
    # Use today's date by default; allow override via env (YYYY-MM-DD)
    date_str = os.getenv("SCREENER_RESULTS_DATE")
    if date_str:
        d = date.fromisoformat(date_str)
    else:
        d = date.today()

    url = build_latest_results_url(d)

    session = requests.Session()
    latest_html = fetch_html(url, session)

    latest_file = META_DIR / "screener_latest_results.html"
    latest_file.write_text(latest_html, encoding="utf-8")

    companies = extract_companies_from_latest(latest_html)

    rows = []
    for c in companies:
        try:
            company_html = fetch_html(c["screener_url"], session)
            pdf_link = extract_latest_pdf_from_company(company_html)
        except Exception as e:
            pdf_link = ""
            # optional: log per-company failure somewhere

        rows.append(
            {
                "company_name": c["company_name"],
                "screener_url": c["screener_url"],
                "result_pdf_link": pdf_link,
            }
        )

    csv_file = write_results_csv(rows)

    write_run_log(
        "ok",
        f"screener_latest date={d.isoformat()} url={url} companies={len(companies)} rows={len(rows)}",
    )

    print(f"Saved {latest_file}")
    print(f"Saved {csv_file} with {len(rows)} rows")


if __name__ == "__main__":
    main()