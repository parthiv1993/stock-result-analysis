# stock-result-analysis

Daily GitHub Actions-based pipeline to fetch NSE/BSE quarterly and annual result PDFs, store metadata, and prepare for later evaluation and summarization.

## What this repo does
- Runs on GitHub Actions daily and manually.
- Downloads result PDFs from NSE/BSE sources (downloader to be expanded next).
- Stores metadata in CSV.
- Keeps code ready for later filters, parsing, and analysis.

## GitHub Actions
This repo includes:
- manual run support via `workflow_dispatch`
- daily run support via cron
- artifact upload for metadata output

## Files
- `.github/workflows/daily-results.yml`
- `src/main.py`
- `requirements.txt`
- `.gitignore`

## Secrets to add later
- `GDRIVE_SERVICE_ACCOUNT_JSON`
- `GDRIVE_FOLDER_ID`
