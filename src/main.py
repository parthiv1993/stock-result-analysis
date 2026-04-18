from pathlib import Path
from datetime import datetime, date
from urllib.parse import urljoin
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


def build_latest_results_url(d: date) -> str:
    return (
        f"{SCREENER_BASE}/results/latest/"
        f"?result_update_date__day={d.day}"
        f"&result_update_date__month={d.month}"
        f"&result_update_date__year={d.year}"
    )


def get_csrf_token(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    token_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
    if token_input and token_input.get("value"):
        return token_input["value"]
    return ""


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

    # Basic success heuristic: if still on login/signup page, fail
    page_text = resp.text.lower()
    if "login to your account" in page_text or "get a free account" in page_text:
        raise RuntimeError("Login failed; still seeing login/signup page")

    return True


def fetch_html(url: str, session: requests.Session) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": SCREENER_BASE,
    }
    r = session.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def extract_companies_from_latest(html: str):
    soup = BeautifulSoup(html, "lxml")
    seen = set()
    companies = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("/company/"):
            continue

        full_url = urljoin(SCREENER_BASE, href.split("?")[0])
        name = a.get_text(" ", strip=True)

        if not name:
            continue
        if full_url in seen:
            continue
        seen.add(full_url)

        companies.append({
            "company_name": name,
            "screener_url": full_url,
            "result_pdf_link": "",
        })

    return companies


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
    email = os.getenv("SCREENER_EMAIL", "").strip()
    password = os.getenv("SCREENER_PASSWORD", "").strip()

    if not email or not password:
        raise RuntimeError("Missing SCREENER_EMAIL / SCREENER_PASSWORD")

    date_str = os.getenv("SCREENER_RESULTS_DATE")
    if date_str:
        d = date.fromisoformat(date_str)
    else:
        d = date.today()

    url = build_latest_results_url(d)

    session = requests.Session()
    login(session, email, password)

    latest_html = fetch_html(url, session)
    save_text("screener_latest_results.html", latest_html)

    companies = extract_companies_from_latest(latest_html)
    csv_file = write_results_csv(companies)

    write_run_log(
        "ok",
        f"screener_logged_in date={d.isoformat()} url={url} companies={len(companies)} rows={len(companies)}"
    )

    print(f"Saved {csv_file} with {len(companies)} rows")


if __name__ == "__main__":
    main()