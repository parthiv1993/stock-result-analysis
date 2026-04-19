import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode, urljoin

from filters import parse_market_cap_cr

SCREENER_BASE = "https://www.screener.in"
LOGIN_URL = f"{SCREENER_BASE}/login/"
LATEST_RESULTS_URL = f"{SCREENER_BASE}/results/latest/"


def login(session, email, password):
    r = session.get(LOGIN_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    csrf_input = soup.select_one('input[name="csrfmiddlewaretoken"]')
    csrf = csrf_input.get("value", "") if csrf_input else ""

    payload = {
        "username": email,
        "password": password,
        "csrfmiddlewaretoken": csrf,
        "next": "",
    }

    resp = session.post(
        LOGIN_URL,
        data=payload,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": LOGIN_URL,
            "Origin": SCREENER_BASE,
        },
        timeout=30,
    )
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

        summary = block.select_one(".font-size-14")
        price = None
        market_cap_text = ""
        pe = None

        if summary:
            spans = [x.get_text(" ", strip=True) for x in summary.find_all("span")]
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