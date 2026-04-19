import requests
import re
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
    s = text.strip().replace(",", "").replace("%", "").replace("₹", "")
    if not s or s.lower() == "none":
        return None
    try:
        return float(s)
    except Exception:
        return None

def _extract_market_cap_from_meta(meta):
    if not meta:
        return "", None
    
    # From span.data-mcap or text
    mcap_span = meta.select_one('span[data-mcap] ~ span.strong')
    if mcap_span:
        mcap_text = mcap_span.get_text(" ", strip=True)
        return f"{mcap_text} Cr", parse_market_cap_cr(f"{mcap_text} Cr")
    
    # Fallback: regex from full text
    import re
    m = re.search(r"M\.Cap\s*₹\s*([\d,]+(?:\.\d+)?)\s*Cr", meta.get_text(" ", strip=True))
    if m:
        return f"{m.group(1)} Cr", parse_market_cap_cr(f"{m.group(1)} Cr")
    
    return "", None

from bs4 import BeautifulSoup, Tag

def _company_sections(soup):
    """
    Yield (header_div, meta_div, details_div) for each stock.

    header_div  = flex-row ... margin-top-32 ... (company + PDF link)
    meta_div    = optional, contains 'Price ... M.Cap ... PE ...'
    details_div = 'bg-base border-radius-8 padding-small responsive-holder' (table wrapper)
    """
    container = soup.select_one("div.mark-visited")
    if not container:
        return []

    sections = []

    current_header = None
    current_meta = None
    current_details = None

    for child in container.children:
        if not isinstance(child, Tag):
            continue

        classes = child.get("class", [])

        # 1) New header: start a new section, flush previous
        if (
            "flex-row" in classes and
            "flex-space-between" in classes and
            "flex-align-center" in classes and
            "margin-top-32" in classes
        ):
            # flush previous section if it had a header
            if current_header is not None:
                sections.append((current_header, current_meta, current_details))

            current_header = child
            current_meta = None
            current_details = None
            continue

        # 2) Details (table wrapper) for current header
        if (
            current_header is not None and
            "bg-base" in classes and
            "border-radius-8" in classes and
            "padding-small" in classes and
            "responsive-holder" in classes
        ):
            current_details = child
            continue

        # 3) Meta row (Price / M.Cap / PE) between header and details
        if current_header is not None and current_meta is None:
            text = child.get_text(" ", strip=True)
            if "Price" in text and "M.Cap" in text:
                current_meta = child
                continue

    # flush last section
    if current_header is not None:
        sections.append((current_header, current_meta, current_details))

    return sections

def _company_blocks(soup):
    items = soup.select("div.mark-visited > div")
    blocks = []

    i = 0
    while i < len(items):
        header = items[i]
        company_a = header.select_one('a[href*="/company/"][href*="quarters"]')

        if not company_a:
            i += 1
            continue

        meta = None
        for j in range(i + 1, min(i + 4, len(items))):
            meta_text = items[j].get_text(" ", strip=True)
            if "Price" in meta_text and "M.Cap" in meta_text:
                meta = items[j]
                break
        table_wrap = items[i + 2] if i + 2 < len(items) else None

        blocks.append((header, meta, table_wrap))
        i += 3

    return blocks

def _extract_meta_values(header, meta):
    if not header and not meta:
        return None, "", None, None
    
    # Combine texts for robust search
    combined = (header.get_text(" ", strip=True) + " " + 
                (meta.get_text(" ", strip=True) if meta else ""))
    
    import re
    
    # Price: first ₹ number after "Price" 
    price = None
    m = re.search(r"Price\s*₹\s*([\d,]+(?:\.\d+)?)", combined)
    if m:
        price = _to_float(m.group(1))
    
    # Market Cap
    mcap_text = ""
    mcap_cr = None
    m = re.search(r"M\.Cap\s*₹\s*([\d,]+(?:\.\d+)?)\s*Cr", combined)
    if m:
        mcap_text = f"{m.group(1)} Cr"
        mcap_cr = parse_market_cap_cr(mcap_text)
    
    # PE
    pe = None
    m = re.search(r"\bPE\s*([\d,]+(?:\.\d+)?)", combined)
    if m:
        pe = _to_float(m.group(1))
    
    return price, mcap_text, mcap_cr, pe

def _extract_qtr_metrics(details_div):
    sales_latest_qtr_cr = None
    sales_yoy_pct = None
    net_profit_latest_qtr_cr = None
    net_profit_yoy_pct = None

    if not details_div:
        return sales_latest_qtr_cr, sales_yoy_pct, net_profit_latest_qtr_cr, net_profit_yoy_pct

    table = details_div.select_one("table.data-table")
    if not table:
        return sales_latest_qtr_cr, sales_yoy_pct, net_profit_latest_qtr_cr, net_profit_yoy_pct

    def parse_yoy_from_row(row):
        if not row:
            return None

        tds = row.find_all("td")
        if len(tds) < 2:
            return None

        yoy_text = tds[1].get_text(" ", strip=True)

        m = re.search(r"([\d,]+(?:\.\d+)?)\s*%", yoy_text)
        if not m:
            m = re.search(r"([\d,]+(?:\.\d+)?)", yoy_text)
        if not m:
            return None

        val = _to_float(m.group(1))
        if val is None:
            return None

        if "⇣" in yoy_text:
            return -val

        return val

    sales_row = table.select_one("tr[data-sales]")
    if sales_row:
        latest_td = sales_row.select_one("td[data-sales-latest-quarter]")
        if latest_td:
            sales_latest_qtr_cr = _to_float(latest_td.get_text(" ", strip=True))
        sales_yoy_pct = parse_yoy_from_row(sales_row)

    np_row = table.select_one("tr[data-net-profit]")
    if np_row:
        latest_td = np_row.select_one("td[data-np-latest-quarter]")
        if latest_td:
            net_profit_latest_qtr_cr = _to_float(latest_td.get_text(" ", strip=True))
        net_profit_yoy_pct = parse_yoy_from_row(np_row)

    return sales_latest_qtr_cr, sales_yoy_pct, net_profit_latest_qtr_cr, net_profit_yoy_pct

def extract_companies(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    for header, meta, details in _company_sections(soup):
        company_a = header.select_one('a[href*="/company/"][href*="quarters"]')
        if not company_a:
            continue

        company_name = company_a.get_text(" ", strip=True)
        screener_url = urljoin(
            SCREENER_BASE,
            company_a.get("href", "").split("?")[0].replace("quarters", "").rstrip("/") + "/#",
        )

        pdf_a = header.select_one('a[href*="/company/source/quarter/"]')
        result_pdf_link = urljoin(SCREENER_BASE, pdf_a.get("href")) if pdf_a else ""

        # Extract price, market cap, PE from header+meta
        price, market_cap_text, market_cap_cr, pe = _extract_meta_values(header, meta)


        # Quarterly metrics
        (
            sales_latest_qtr_cr,
            sales_yoy_pct,
            net_profit_latest_qtr_cr,
            net_profit_yoy_pct,
        ) = _extract_qtr_metrics(details)

        # Optional debug
        if meta:
            meta_text = meta.get_text(" ", strip=True)
            print("\nMETA:", company_name, "=>", meta_text[:200])
        print(f"{company_name}: price={price}, mcap={market_cap_text}, pe={pe},sales_latest_qtr_cr={sales_latest_qtr_cr},sales_yoy_pct={sales_yoy_pct},net_profit_latest_qtr_cr={net_profit_latest_qtr_cr},net_profit_yoy_pct={net_profit_yoy_pct}")


      

        rows.append({
            "company_name": company_name,
            "screener_url": screener_url,
            "result_pdf_link": result_pdf_link,
            "price": price,
            "market_cap_text": market_cap_text,
            "market_cap_cr": market_cap_cr,
            "pe": pe,
            "sales_latest_qtr_cr": sales_latest_qtr_cr,
            "sales_yoy_pct": sales_yoy_pct,
            "net_profit_latest_qtr_cr": net_profit_latest_qtr_cr,
            "net_profit_yoy_pct": net_profit_yoy_pct,
        })

    return rows

def fetch_latest_results(session, result_date=None):
    url = build_latest_url(result_date)
    r = session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    return r.text