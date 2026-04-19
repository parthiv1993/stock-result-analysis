import re


def to_float(value):
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        m = re.search(r"-?\d+(\.\d+)?", s)
        return float(m.group()) if m else None


def parse_market_cap_cr(value):
    if value is None:
        return None

    s = str(value).strip().replace(",", "")
    if not s:
        return None

    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None

    num = float(m.group(1))
    lower = s.lower()

    if "lac" in lower or "lakh" in lower:
        return num / 100
    if "cr" in lower or "crore" in lower:
        return num
    if "bn" in lower or "billion" in lower:
        return num * 100

    return num


def filter_market_cap_above(rows, min_market_cap_cr=500):
    out = []
    for row in rows:
        mc = row.get("market_cap_cr")
        if mc is not None and mc > min_market_cap_cr:
            out.append(row)
    return out