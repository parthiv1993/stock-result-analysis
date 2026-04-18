from pathlib import Path
from datetime import datetime, date
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
import csv
import os
import requests
import re

BASE = Path(__file__).resolve().parents[1]
META_DIR = BASE / "data" / "metadata"
META_DIR.mkdir(parents=True, exist_ok=True)

SCREENER_BASE = "https://www.screener.in"
LOGIN_URL = f"{SCREENER_BASE}/login/"
LATEST_RESULTS_URL = f"{SCREENER_BASE}/results/latest/"


def write_run_log(status: str, notes: str):
    file_path = META_DIR / "runs.csv"
    exists = file_path.exists()
    with file_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["run_utc", "status", "notes"])
        writer.writerow([datetime.utcnow().isoformat() + "Z", status, notes])


def save_text(filename: str, content: str):
    out = META_DIR / filename
    out.write_text(content, encoding="utf-8")
    return out


def get_csrf_token(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    token_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
    return token_input.get("value", "") if token_input else ""


def login(session: requests.Session, email: str, password: str):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": LOGIN_URL,
    }

    r = session.get(LOGIN_URL, headers=headers, timeout=30)
    r.raise_for_status()
    login_html = r.text
    save_text("screener_login_page.html", login_html)

    csrf_token = get_csrf_token(login_html)
    if not csrf_token:
        raise RuntimeError("Could not find csrfmiddlewaretoken on login page")

    payload = {
        "csrfmiddlewaretoken": csrf_token,
        "username": email,
        "password": password,
        "next": "",
    }

    post_headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": LOGIN_URL,
        "Origin": SCREENER_BASE,
    }

    resp = session.post(LOGIN_URL, data=payload, headers=post_headers, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    save_text("screener_login_response.html", resp.text)

    page_text = resp.text.lower()
    if "login to your account" in page_text or "get a free account" in page_text:
        raise RuntimeError("Login failed; still seeing login/signup page")


def fetch_html(url: str, session: requests.Session) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": SCREENER_BASE,
    }
    r = session.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def build_date_url(d: date) -> str:
    return (
        f"{LATEST_RESULTS_URL}"
        f"?result_update_date__day={d.day}"
        f"&result_update_date__month={d.month}"
        f"&result_update_date__year={d.year}"
    )


def extract_rows_from_latest(html: str):
    soup = BeautifulSoup(html, "lxml")

    anchors = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = urljoin(SCREENER_BASE, href)

        anchors.append({
            "text": a.get_text(" ", strip=True),
            "href": href,
            "full": full,
        })

    rows = []
    i = 0
    while i < len(anchors):
        a = anchors[i]
        href = a["href"]

        if href.startswith("/company/") and "/source/quarter/" not in href:
            company_name = a["text"].strip()
            screener_url = a["full"].split("?")[0]
            result_pdf_link = ""

            # look ahead a few anchors for the associated PDF/source link
            for j in range(i + 1, min(i + 6, len(anchors))):
                nxt = anchors[j]
                if "/company/source/quarter/" in nxt["href"]:
                    result_pdf_link = nxt["full"]
                    break
                # stop if next company starts
                if nxt["href"].startswith("/company/") and "/source/quarter/" not in nxt["href"]:
                    break

            rows.append({
                "company_name": company_name,
                "screener_url": screener_url,
                "result_pdf_link": result_pdf_link,
            })

        i += 1

    # dedupe
    deduped = []
    seen = set()
    for row in rows:
        key = (row["company_name"], row["screener_url"], row["result_pdf_link"])
        if key not in seen:
            seen.add(key)
            deduped.append(row)

    return deduped


def extract_next_page(html: str):
    soup = BeautifulSoup(html, "lxml")

    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True).lower()
        href = a["href"].strip()

        if text in {"next", "next page", "›", "→"}:
            return urljoin(SCREENER_BASE, href)

    return None


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


def scrape_single_date(session: requests.Session, d: date):
    url = build_date_url(d)
    html = fetch_html(url, session)
    save_text("screener_latest_results.html", html)
    rows = extract_rows_from_latest(html)
    return url, rows


def scrape_all_pages(session: requests.Session):
    url = LATEST_RESULTS_URL
    all_rows = []
    visited = set()
    page_num = 1

    while url and url not in visited:
        visited.add(url)
        html = fetch_html(url, session)

        if page_num == 1:
            save_text("screener_latest_results.html", html)
        else:
            save_text(f"screener_latest_results_page_{page_num}.html", html)

        rows = extract_rows_from_latest(html)
        all_rows.extend(rows)

        next_url = extract_next_page(html)
        url = next_url
        page_num += 1

        if page_num > 100:
            break

    deduped = []
    seen = set()
    for row in all_rows:
        key = (row["company_name"], row["screener_url"], row["result_pdf_link"])
        if key not in seen:
            seen.add(key)
            deduped.append(row)

    return deduped


def main():
    email = os.getenv("SCREENER_EMAIL", "").strip()
    password = os.getenv("SCREENER_PASSWORD", "").strip()

    if not email or not password:
        raise RuntimeError("Missing SCREENER_EMAIL / SCREENER_PASSWORD")

    date_str = os.getenv("SCREENER_RESULTS_DATE", "").strip()

    session = requests.Session()
    login(session, email, password)

    if date_str:
        d = date.fromisoformat(date_str)
        url, rows = scrape_single_date(session, d)
        mode = f"date={d.isoformat()} url={url}"
    else:
        rows = scrape_all_pages(session)
        mode = "all_pages"

    csv_file = write_results_csv(rows)

    write_run_log(
        "ok",
        f"screener_logged_in mode={mode} rows={len(rows)}"
    )

    print(f"Saved {csv_file} with {len(rows)} rows")


if __name__ == "__main__":
    main()