from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import csv
import requests
import re

BASE = Path(__file__).resolve().parents[1]
META_DIR = BASE / "data" / "metadata"
META_DIR.mkdir(parents=True, exist_ok=True)

BSE_RESULTS_URL = "https://www.bseindia.com/corporates/Comp_Resultsnew.aspx"

def write_run_log(status: str, notes: str):
    file_path = META_DIR / "runs.csv"
    exists = file_path.exists()
    with file_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["run_utc", "status", "notes"])
        writer.writerow([datetime.now(timezone.utc).isoformat(), status, notes])

def fetch_bse_page():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.bseindia.com/",
    }
    session = requests.Session()
    r = session.get(BSE_RESULTS_URL, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text

def save_text(filename: str, content: str):
    out = META_DIR / filename
    out.write_text(content, encoding="utf-8")
    return out

def extract_debug_info(html: str):
    soup = BeautifulSoup(html, "lxml")

    hidden_fields = []
    for inp in soup.select("input[type='hidden']"):
        hidden_fields.append({
            "name": inp.get("name", ""),
            "id": inp.get("id", ""),
            "value_prefix": (inp.get("value", "")[:120]),
        })

    scripts = []
    for s in soup.find_all("script", src=True):
        scripts.append(urljoin(BSE_RESULTS_URL, s["src"]))

    candidates = set()

    # URLs embedded in HTML / JS
    for match in re.findall(r"""https?://[^\s"'<>]+|/[A-Za-z0-9_\-./?=&%]+""", html):
        if any(token in match.lower() for token in [
            "results", "xbrl", "announcement", "attach", "corp", "ajax", "details", ".asmx", ".ashx", ".svc"
        ]):
            candidates.add(urljoin(BSE_RESULTS_URL, match))

    # Common ASP.NET postback clues
    for match in re.findall(r"__doPostBack\('([^']+)'", html):
        candidates.add(f"POSTBACK::{match}")

    return hidden_fields, scripts, sorted(candidates)

def write_hidden_fields_csv(hidden_fields):
    out = META_DIR / "bse_hidden_fields.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "id", "value_prefix"])
        writer.writeheader()
        writer.writerows(hidden_fields)
    return out

def write_scripts_csv(scripts):
    out = META_DIR / "bse_script_urls.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["script_url"])
        for s in scripts:
            writer.writerow([s])
    return out

def write_candidates_csv(candidates):
    out = META_DIR / "bse_candidate_endpoints.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate"])
        for c in candidates:
            writer.writerow([c])
    return out

def main():
    html = fetch_bse_page()
    html_file = save_text("bse_results_page.html", html)

    hidden_fields, scripts, candidates = extract_debug_info(html)

    hidden_csv = write_hidden_fields_csv(hidden_fields)
    scripts_csv = write_scripts_csv(scripts)
    candidates_csv = write_candidates_csv(candidates)

    write_run_log(
        "ok",
        f"fetched_bse_results_page bytes={len(html)} html={html_file.name} hidden={len(hidden_fields)} scripts={len(scripts)} candidates={len(candidates)}"
    )

    print(f"Saved {html_file}")
    print(f"Saved {hidden_csv}")
    print(f"Saved {scripts_csv}")
    print(f"Saved {candidates_csv}")

if __name__ == "__main__":
    main()