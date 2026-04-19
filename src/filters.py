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
    return num


def filter_market_cap_above(rows, min_cr):
    out = []
    for row in rows:
        mc = row.get("market_cap_cr")
        if mc is not None and mc > min_cr:
            out.append(row)
    return out