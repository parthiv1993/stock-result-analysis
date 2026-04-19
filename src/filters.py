from __future__ import annotations

import math
import re


def parse_market_cap_to_cr(value: str | None) -> float | None:
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
    if "cr" in lower or "crore" in lower:
        return num
    if "bn" in lower or "billion" in lower:
        return num * 100.0

    return num


def market_cap_above(rows: list[dict], min_cr: float) -> list[dict]:
    out = []
    for row in rows:
        mc = row.get("market_cap_cr")
        if mc is None:
            continue
        if mc > min_cr:
            out.append(row)
    return out


def safe_float(v):
    try:
        x = float(v)
        if math.isnan(x):
            return None
        return x
    except Exception:
        return None