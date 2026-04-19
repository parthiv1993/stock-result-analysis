import re

def parse_market_cap_cr(value):
    if value is None:
        return None

    s = str(value).strip().replace(",", "")
    if not s or s == "-" or s.lower() == "nan":
        return None

    m = re.search(r"([\d.]+)", s)
    if not m:
        return None

    num = float(m.group(1))
    lower = s.lower()

    if "lac" in lower or "lakh" in lower:
        return num / 100.0
    if "bn" in lower or "billion" in lower:
        return num * 100.0
    if "cr" in lower or "crore" in lower:
        return num

    return None


def _to_float_or_none(value):
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if not s or s == "-" or s.lower() == "nan":
        return None
    try:
        return float(s)
    except Exception:
        return None


def filter_market_cap_above(rows, min_cr):
    out = []

    for row in rows:
        mc = row.get("market_cap_cr")
        if mc is None:
            mc = parse_market_cap_cr(row.get("market_cap_text"))

        pe = _to_float_or_none(row.get("pe"))
        sales_yoy = _to_float_or_none(row.get("sales_yoy_pct"))
        profit_yoy = _to_float_or_none(row.get("net_profit_yoy_pct"))
        latest_profit = _to_float_or_none(row.get("net_profit_latest_qtr_cr"))

        if mc is None or mc <= min_cr:
            continue

        if latest_profit is None or latest_profit <= 0:
            continue

        if sales_yoy is None or sales_yoy <= 10:
            continue

        if profit_yoy is None or profit_yoy <= 10:
            continue

        if pe is not None and pe >= 100:
            continue

        row["market_cap_cr"] = mc
        row["pe"] = pe
        row["sales_yoy_pct"] = sales_yoy
        row["net_profit_yoy_pct"] = profit_yoy
        row["net_profit_latest_qtr_cr"] = latest_profit
        out.append(row)

    return out