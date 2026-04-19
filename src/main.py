import csv
import os
from pathlib import Path
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.table import Table, TableStyleInfo

from filters import parse_market_cap_cr, filter_market_cap_above


BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SCREENER_BASE = "https://www.screener.in"
LOGIN_URL = f"{SCREENER_BASE}/login/"
LATEST_RESULTS_URL = f"{SCREENER_BASE}/results/latest/"


def login(session, email, password):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = session.get(LOGIN_URL, headers=headers, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    csrf = ""
    csrf_input = soup.select_one('input[name="csrfmiddlewaretoken"]')
    if csrf_input:
        csrf = csrf_input.get("value", "")

    payload = {
        "username": email,
        "password": password,
        "csrfmiddlewaretoken": csrf,
        "next": "",
    }

    post_headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": LOGIN_URL,
        "Origin": SCREENER_BASE,
    }

    resp = session.post(LOGIN_URL, data=payload, headers=post_headers, timeout=30)
    resp.raise_for_status()

    if "login to your account" in resp.text.lower():
        raise RuntimeError("Login failed")


def build_latest_url(result_date=None):
    params = {"all": ""}
    if result_date:
        yyyy, mm, dd = result_date.split("-")
        params["result_update_date__day"] = str(int(dd))
        params["result_update_date__month"] = str(int(mm))
        params["result_update_date__year"] = yyyy
    return f"{LATEST_RESULTS_URL}?{urlencode(params)}"


def extract_companies(html):
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select("main .margin-top-32")
    rows = []

    for block in blocks:
        company_a = block.select_one('a[href*="/company/"][href*="quarters"]')
        if not company_a:
            continue

        company_name = company_a.get_text(" ", strip=True)
        company_url = urljoin(SCREENER_BASE, company_a.get("href", "").split("?")[0])

        pdf_a = block.select_one('a[href*="/company/source/quarter/"]')
        pdf_url = urljoin(SCREENER_BASE, pdf_a.get("href")) if pdf_a else ""

        info = block.select_one(".font-size-14")
        price = None
        market_cap_text = ""
        pe = None

        if info:
            spans = [x.get_text(" ", strip=True) for x in info.find_all("span")]
            for i, txt in enumerate(spans):
                t = txt.lower()
                if t == "price" and i + 1 < len(spans):
                    try:
                        price = float(spans[i + 1].replace(",", ""))
                    except Exception:
                        price = None
                elif "m.cap" in t and i + 1 < len(spans):
                    market_cap_text = spans[i + 1]
                elif t == "pe" and i + 1 < len(spans):
                    try:
                        pe = float(spans[i + 1].replace(",", ""))
                    except Exception:
                        pe = None

        market_cap_cr = parse_market_cap_cr(market_cap_text)

        table = block.find_next("table")
        sales_latest = None
        sales_yoy = None
        np_latest = None
        np_yoy = None

        if table:
            sales_row = table.select_one("tr[data-sales]")
            if sales_row:
                sales_latest_td = sales_row.select_one("td[data-sales-latest-quarter]")
                if sales_latest_td:
                    try:
                        sales_latest = float(sales_latest_td.get_text(strip=True).replace(",", ""))
                    except Exception:
                        sales_latest = None
                tds = sales_row.find_all("td")
                if len(tds) >= 2:
                    yoy_text = tds[1].get_text(" ", strip=True).replace("%", "").replace(",", "")
                    try:
                        sales_yoy = float(yoy_text)
                    except Exception:
                        sales_yoy = None

            np_row = table.select_one("tr[data-net-profit]")
            if np_row:
                np_latest_td = np_row.select_one("td[data-np-latest-quarter]")
                if np_latest_td:
                    try:
                        np_latest = float(np_latest_td.get_text(strip=True).replace(",", ""))
                    except Exception:
                        np_latest = None
                tds = np_row.find_all("td")
                if len(tds) >= 2:
                    yoy_text = tds[1].get_text(" ", strip=True).replace("%", "").replace(",", "")
                    try:
                        np_yoy = float(yoy_text)
                    except Exception:
                        np_yoy = None

        rows.append({
            "company_name": company_name,
            "company_url": company_url,
            "pdf_url": pdf_url,
            "price": price,
            "market_cap_text": market_cap_text,
            "market_cap_cr": market_cap_cr,
            "pe": pe,
            "sales_latest_qtr_cr": sales_latest,
            "sales_yoy_pct": sales_yoy,
            "net_profit_latest_qtr_cr": np_latest,
            "net_profit_yoy_pct": np_yoy,
        })

    return rows


def write_csv(rows, path):
    if not rows:
        return

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_excel(rows, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Filtered Results"

    headers = [
        "Company Name",
        "Company URL",
        "PDF URL",
        "Price",
        "Market Cap",
        "Market Cap (Cr)",
        "PE",
        "Sales Latest Qtr (Cr)",
        "Sales YoY (%)",
        "Net Profit Latest Qtr (Cr)",
        "Net Profit YoY (%)",
    ]
    ws.append(headers)

    for row in rows:
        ws.append([
            row.get("company_name"),
            row.get("company_url"),
            row.get("pdf_url"),
            row.get("price"),
            row.get("market_cap_text"),
            row.get("market_cap_cr"),
            row.get("pe"),
            row.get("sales_latest_qtr_cr"),
            row.get("sales_yoy_pct"),
            row.get("net_profit_latest_qtr_cr"),
            row.get("net_profit_yoy_pct"),
        ])

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True, name="Calibri")
    body_font = Font(name="Calibri")
    link_font = Font(name="Calibri", color="0000EE", underline="single")
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center")
    right = Alignment(horizontal="right", vertical="center")

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center

    for row_idx in range(2, ws.max_row + 1):
        for col_idx in range(1, ws.max_column + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = body_font
            cell.alignment = left if col_idx in (1, 2, 3, 5) else right

        for col_idx in (2, 3):
            cell = ws.cell(row=row_idx, column=col_idx)
            if cell.value:
                cell.hyperlink = cell.value
                cell.font = link_font
                cell.alignment = left

    widths = {
        "A": 28, "B": 42, "C": 42, "D": 12, "E": 16,
        "F": 16, "G": 10, "H": 20, "I": 14, "J": 23, "K": 18
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    ws.freeze_panes = "A2"

    if ws.max_row > 1:
        ref = f"A1:K{ws.max_row}"
        table = Table(displayName="FilteredResults", ref=ref)
        style = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )
        table.tableStyleInfo = style
        ws.add_table(table)

    wb.save(path)


def main():
    email = os.getenv("SCREENER_EMAIL", "").strip()
    password = os.getenv("SCREENER_PASSWORD", "").strip()
    result_date = os.getenv("SCREENER_RESULTS_DATE", "").strip()

    if not email or not password:
        raise RuntimeError("Missing SCREENER_EMAIL or SCREENER_PASSWORD")

    session = requests.Session()
    login(session, email, password)

    url = build_latest_url(result_date if result_date else None)
    resp = session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()

    html_path = OUT_DIR / "screener_latest_results.html"
    html_path.write_text(resp.text, encoding="utf-8")

    all_rows = extract_companies(resp.text)
    filtered_rows = filter_market_cap_above(all_rows, 500)

    write_csv(all_rows, OUT_DIR / "all_results.csv")
    write_csv(filtered_rows, OUT_DIR / "filtered_results_mcap_above_500cr.csv")
    write_excel(filtered_rows, OUT_DIR / "filtered_results_mcap_above_500cr.xlsx")

    print(f"All rows: {len(all_rows)}")
    print(f"Filtered rows (>500 Cr): {len(filtered_rows)}")


if __name__ == "__main__":
    main()