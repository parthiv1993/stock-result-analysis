import os
from pathlib import Path

import requests

import excel_writer  # ← ADD THIS
print("Excel writer loaded from:", excel_writer.write_excel.__code__.co_filename)  # ← ADD THIS

from excel_writer import write_csv, write_excel
from filters import filter_market_cap_above
from scrape import build_latest_url, extract_companies, login


BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)


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

    (OUT_DIR / "screener_latest_results.html").write_text(resp.text, encoding="utf-8")

    all_rows = extract_companies(resp.text)
    filtered_rows = filter_market_cap_above(all_rows, 500)

    write_csv(all_rows, OUT_DIR / "all_results.csv")
    write_csv(filtered_rows, OUT_DIR / "filtered_results_mcap_above_500cr.csv")


    print(f"All rows: {len(all_rows)}")
    print(f"Filtered rows (>500 Cr): {len(filtered_rows)}")


if __name__ == "__main__":
    main()