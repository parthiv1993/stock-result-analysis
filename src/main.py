from pathlib import Path
from datetime import datetime, date
from urllib.parse import urlencode, urljoin
from bs4 import BeautifulSoup
import csv
import os
import requests

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

    resp = session.post(
        LOGIN_URL,
        data=payload,
        headers=post_headers,
        timeout=30,
        allow_redirects=True,
    )
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


def build_results_url(d: date | None = None, use_all: bool = False, page: int | None = None) -> str:
    params = {}

    if use_all:
        params["all"] = ""

    if d:
        params["result_update_date__day"] = d.day
        params["result_update_date__month"] = d.month
        params["result_update_date__year"] = d.year

    if page and page > 1:
        params["p"] = page

    qs = urlencode(params)
    return f"{LATEST_RESULTS_URL}?{qs}" if qs else LATEST_RESULTS_URL


def normalize_company_url(href: str) -> str:
    return urljoin(SCREENER_BASE, href.split("?")[0])


def normalize_source_url(href: str) -> str:
    return urljoin(SCREENER_BASE, href)


def extract_rows_from_latest(html: str):
    soup = BeautifulSoup(html, "lxml")

    anchors = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(" ", strip=True)
        anchors.append({"href": href, "text": text})

    rows = []
    seen_company_urls = set()

    i = 0
    while i < len(anchors):
        href = anchors[i]["href"]
        text = anchors[i]["text"]

        if href.startswith("/company/") and "/source/quarter/" not in href:
            company_url = normalize_company_url(href)
            company_name = text.strip()

            if company_name and company_url not in seen_company_urls:
                result_pdf_link = ""

                for j in range(i + 1, min(i + 10, len(anchors))):
                    next_href = anchors[j]["href"]

                    if "/company/source/quarter/" in next_href:
                        result_pdf_link = normalize_source_url(next_href)
                        break

                    if next_href.startswith("/company/") and "/source/quarter/" not in next_href:
                        break

                rows.append({
                    "company_name": company_name,
                    "screener_url": company_url,
                    "result_pdf_link": result_pdf_link,
                })
                seen_company_urls.add(company_url)

        i += 1

    deduped = []
    seen = set()
    for row in rows:
        key = (row["company_name"], row["screener_url"], row["result_pdf_link"])
        if key not in seen:
            seen.add(key)
            deduped.append(row)

    return deduped


def scrape_one_url(session: requests.Session, url: str, save_name: str | None = None):
    html = fetch_html(url, session)
    if save_name:
        save_text(save_name, html)
    rows = extract_rows_from_latest(html)
    return rows, html


def scrape_all_mode(session: requests.Session, d: date | None = None):
    all_rows = []

    all_url = build_results_url(d=d, use_all=True)
    rows_all, html_all = scrape_one_url(session, all_url, "screener_latest_results.html")
    all_rows.extend(rows_all)

    if len(rows_all) > 0:
        return dedupe_rows(all_rows), f"all_url={all_url}"

    page = 1
    while True:
        paged_url = build_results_url(d=d, use_all=False, page=page)
        save_name = "screener_latest_results.html" if page == 1 else f"screener_latest_results_page_{page}.html"
        rows, _ = scrape_one_url(session, paged_url, save_name)

        if not rows:
            break

        before = len(all_rows)
        all_rows.extend(rows)
        after = len(dedupe_rows(all_rows))

        if after == len(dedupe_rows(all_rows[:before])):
            break

        page += 1
        if page > 100:
            break

    return dedupe_rows(all_rows), f"paged_fallback last_page={page - 1}"


def dedupe_rows(rows):
    deduped = []
    seen = set()
    for row in rows:
        key = (row["company_name"], row["screener_url"], row["result_pdf_link"])
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    return deduped


def main():
    email = os.getenv("SCREENER_EMAIL", "").strip()
    password = os.getenv("SCREENER_PASSWORD", "").strip()
    date_str = os.getenv("SCREENER_RESULTS_DATE", "").strip()

    if not email or not password:
        raise RuntimeError("Missing SCREENER_EMAIL / SCREENER_PASSWORD")

    d = date.fromisoformat(date_str) if date_str else None

    session = requests.Session()
    login(session, email, password)

    rows, mode_notes = scrape_all_mode(session, d=d)

    csv_file = write_results_csv(rows)

    mode = f"date={d.isoformat()}" if d else "date=all"
    write_run_log(
        "ok",
        f"screener_logged_in mode={mode} {mode_notes} rows={len(rows)}"
    )

    print(f"Saved {csv_file} with {len(rows)} rows")


if __name__ == "__main__":
    main()