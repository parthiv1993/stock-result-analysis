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


def _to_float(text):
    if text is None:
        return None
    s = text.strip().replace(",", "").replace("%", "")
    if not s or s.lower() == "none":
        return None
    try:
        return float(s)
    except Exception:
        return None


def extract_companies(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    headers = soup.select(
        "main div.flex-row.flex-space-between.flex-align-center.margin-top-32"
    )

    for header in headers:
        company_a = header.select_one('a[href*="/company/"][href*="quarters"]')
        if not company_a:
            continue

        company_name = company_a.get_text(" ", strip=True)
        screener_url = urljoin(
            SCREENER_BASE,
            company_a.get("href", "").split("?")[0].replace("quarters", "").rstrip("/"),
        )

        pdf_a = header.select_one('a[href*="/company/source/quarter/"]')
        result_pdf_link = urljoin(SCREENER_BASE, pdf_a.get("href")) if pdf_a else ""

        meta = header.find_next_sibling("div")
        price = None
        market_cap_text = ""
        pe = None

        if meta and "font-size-14" in (meta.get("class") or []):
            strongs = meta.find_all("span", class_="strong")

            price_label = meta.find("span", string=lambda s: s and s.strip().lower() == "price")
            if price_label:
                strong = price_label.find_next("span", class_="strong")
                price = _to_float(strong.get_text(" ", strip=True) if strong else None)

            mcap_label = meta.find("span", attrs={"data-mcap": True})
            if mcap_label:
                strong = mcap_label.find_next("span", class_="strong")
                if strong:
                    market_cap_text = f"{strong.get_text(' ', strip=True)} Cr"

            pe_label = meta.find("span", string=lambda s: s and s.strip().lower() == "pe")
            if pe_label:
                strong = pe_label.find_next("span", class_="strong")
                pe = _to_float(strong.get_text(" ", strip=True) if strong else None)

        market_cap_cr = parse_market_cap_cr(market_cap_text)

        table_wrap = meta.find_next_sibling("div") if meta else None
        table = table_wrap.find("table") if table_wrap else None

        sales_latest = None
        sales_yoy = None
        np_latest = None
        np_yoy = None

        if table:
            sales_row = table.select_one("tr[data-sales]")
            if sales_row:
                sales_latest_td = sales_row.select_one("td[data-sales-latest-quarter]")
                sales_latest = _to_float(
                    sales_latest_td.get_text(" ", strip=True) if sales_latest_td else None
                )
                tds = sales_row.find_all("td")
                if len(tds) >= 2:
                    sales_yoy = _to_float(tds[1].get_text(" ", strip=True))

            np_row = table.select_one("tr[data-net-profit]")
            if np_row:
                np_latest_td = np_row.select_one("td[data-np-latest-quarter]")
                np_latest = _to_float(
                    np_latest_td.get_text(" ", strip=True) if np_latest_td else None
                )
                tds = np_row.find_all("td")
                if len(tds) >= 2:
                    np_yoy = _to_float(tds[1].get_text(" ", strip=True))

        rows.append({
            "company_name": company_name,
            "screener_url": screener_url,
            "result_pdf_link": result_pdf_link,
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