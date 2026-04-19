from pathlib import Path
from datetime import datetime, date
from urllib.parse import urlencode, urljoin
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter
import csv
import os
import requests

from filters import parse_market_cap_to_cr, market_cap_above


BASE = Path(__file__).resolve().parents[1]
META_DIR = BASE / "data" / "metadata"
META_DIR.mkdir(parents=True, exist_ok=True)

SCREENER_BASE = "https://www.screener.in"
LOGIN_URL = f"{SCREENER_BASE}/login/"
LATEST_RESULTS_URL = f"{SCREENER_BASE}/results/latest/"
MIN_MARKET_CAP_CR = 500


HDR_FILL = PatternFill("solid", fgColor="1F4E78")
HDR_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
BODY_FONT = Font(name="Calibri", size=11, color="000000")
LINK_FONT = Font(name="Calibri", size=11, color="0000FF", underline="single")
CENTER = Alignment(horizontal="center", vertical="center")
LEFT = Alignment(horizontal="left", vertical="center")
RIGHT = Alignment(horizontal="right", vertical="center")


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


def write_results_csv(rows, filename="screener_results.csv"):
    out = META_DIR / filename
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "company_name",
                "screener_url",
                "market_cap_text",
                "market_cap_cr",
                "result_pdf_link",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return out


def write_results_xlsx(rows, filename="screener_results.xlsx"):
    out = META_DIR / filename
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"

    headers = [
        "Company Name",
        "Screener URL",
        "Market Cap",
        "Market Cap (Cr)",
        "Result PDF Link",
    ]
    ws.append(headers)

    for row in rows:
        ws.append([
            row.get("company_name", ""),
            row.get("screener_url", ""),
            row.get("market_cap_text", ""),
            row.get("market_cap_cr", ""),
            row.get("result_pdf_link", ""),
        ])

    for cell in ws[1]:
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.alignment = CENTER

    for r in range(2, ws.max_row + 1):
        ws.cell(r, 1).font = BODY_FONT
        ws.cell(r, 1).alignment = LEFT

        ws.cell(r, 2).font = LINK_FONT
        ws.cell(r, 2).alignment = LEFT
        if ws.cell(r, 2).value:
            ws.cell(r, 2).hyperlink = ws.cell(r, 2).value

        ws.cell(r, 3).font = BODY_FONT
        ws.cell(r, 3).alignment = RIGHT

        ws.cell(r, 4).font = BODY_FONT
        ws.cell(r, 4).alignment = RIGHT
        ws.cell(r, 4).number_format = '#,##0.00'

        ws.cell(r, 5).font = LINK_FONT
        ws.cell(r, 5).alignment = LEFT
        if ws.cell(r, 5).value:
            ws.cell(r, 5).hyperlink = ws.cell(r, 5).value

    widths = {
        "A": 28,
        "B": 45,
        "C": 18,
        "D": 18,
        "E": 45,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    ws.freeze_panes = "A2"

    if ws.max_row >= 2:
        table = Table(displayName="ScreenerResults", ref=f"A1:E{ws.max_row}")
        style = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )
        table.tableStyleInfo = style
        ws.add_table(table)

    wb.save(out)
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
    save_text("screener_login_page.html", r.text)

    csrf_token = get_csrf_token(r.text)
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

    text = resp.text.lower()
    if "login to your account" in text or "get a free account" in text:
        raise RuntimeError("Login failed")


def fetch_html(url: str, session: requests.Session) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": SCREENER_BASE,
    }
    r = session.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def build_results_url(d: date | None = None, use_all: bool = True) -> str:
    params = {}

    if use_all:
        params["all"] = ""

    if d:
        params["result_update_date__day"] = d.day
        params["result_update_date__month"] = d.month
        params["result_update_date__year"] = d.year

    qs = urlencode(params)
    return f"{LATEST_RESULTS_URL}?{qs}" if qs else LATEST_RESULTS_URL


def normalize_company_url(href: str) -> str:
    return urljoin(SCREENER_BASE, href.split("?")[0])


def normalize_url(href: str) -> str:
    return urljoin(SCREENER_BASE, href)


def extract_rows_from_latest(html: str):
    soup = BeautifulSoup(html, "lxml")
    rows = []
    seen = set()

    