# Screener Latest Results Scraper

This project scrapes the **Latest quarterly results** page on Screener, extracts company-level result entries, applies reusable filters, and exports both CSV and Excel outputs. The current workflow already captures market capitalization from the latest-results page and generates filtered outputs for companies with **market cap above 500 Cr**.[cite:630][cite:800][cite:802]

## What the scraper does

The scraper logs in to Screener, opens the **Latest quarterly results** page, and pulls repeated company result blocks that include a company link, a PDF link, market-cap text, and quarterly result rows such as sales and net profit.[cite:630]

It currently produces two main output types:
- a full dataset with all scraped rows and parsed market-cap values.[cite:800]
- a filtered dataset in Excel for companies above 500 Cr market cap.[cite:802]

## Why the code should stay modular

The project should remain split into smaller files rather than moving everything back into `main.py`. The latest-results page contains repeated blocks with multiple fields and nested quarterly tables, so parsing, filtering, and Excel writing are separate concerns and are easier to maintain independently.[cite:630]

A recommended structure is:

- `main.py` — orchestration only: login, fetch page, call parser/helpers, and write outputs.[cite:630]
- `extractors.py` — HTML parsing for company blocks, links, market cap, PE, and quarterly metrics from the latest-results page.[cite:630]
- `filters.py` — reusable business rules such as `market_cap > 500 Cr`, future PE filters, or profitability filters.[cite:802]
- `excel_writer.py` — workbook creation, styling, hyperlinks, table formatting, and filtered export generation.[cite:802]

## Extraction approach

The latest-results page supports `?all=` and shows the full list of current result entries; the saved page contains **72 results** in the captured run.[cite:630]

Each company is represented by a repeated block containing:
- a company page link such as `/company/HDFCBANK/consolidated/` or similar variants.[cite:630]
- a quarterly-result PDF link under `/company/source/quarter/...`.[cite:630]
- summary metadata such as price, market cap, and often PE.[cite:630]
- a small quarterly table with rows like Sales, EBIDT, Net Profit, and EPS across latest and prior quarters.[cite:630]

Because these values are grouped visually into repeated sections, the parser should work **block-by-block** or **row-by-row**, not by scanning every anchor globally. This avoids mismatches like treating `PDF` or detached links as separate companies.[cite:630][cite:800]

## Filtering logic

The current primary business rule is:

- include only companies where parsed market cap in crore is **greater than 500**.[cite:802]

The raw CSV shows both companies below and above that threshold, such as Virgo Global at **5.84 Cr** and HDFC Bank at **12,31,316 Cr**, which confirms why a separate filtering stage is useful instead of applying the rule during raw extraction.[cite:800]

The filtered Excel output includes examples such as HDFC Bank, ICICI Bank, Jio Financial, TCS, Wipro, CRISIL, and Angel One, all of which exceed the 500 Cr cutoff.[cite:802]

## Current outputs

### Full CSV

The full CSV contains rows for all scraped companies and currently includes these core columns:
- company name
- Screener URL
- market-cap text
- parsed market-cap in crore
- result PDF link[cite:800]

### Filtered Excel

The filtered Excel contains only rows with market cap above 500 Cr and includes clickable company and PDF links along with parsed market-cap values.[cite:802]

## Known issues and observations

The current extraction is functionally working for market-cap filtering, but the outputs show signs that the parser still needs refinement. The filtered workbook summary includes repeated `TITLE Results` fragments and extra URLs in places where only clean rows should appear, which suggests the page parsing is still catching unrelated content in some cases.[cite:802]

The raw CSV also shows that some entries have incomplete market metadata, such as rows where market-cap text is blank or sparse, which means null-handling and block boundary detection should remain part of the parser design.[cite:800]

## Recommended next improvements

1. Move all HTML parsing into `extractors.py` and build around one company block at a time.[cite:630]
2. Keep market-cap parsing and thresholds in `filters.py` so additional screening rules can be added easily.[cite:800][cite:802]
3. Keep Excel formatting isolated in `excel_writer.py` so file-output changes do not affect scraping logic.[cite:802]
4. Add more extracted fields from the latest-results page, especially PE and quarterly growth fields already visible in the saved HTML.[cite:630]
5. In a second phase, fetch each company page only if longer-horizon metrics such as ROE history, shareholding trend, or multi-year CAGR values are needed.[cite:630]

## Suggested file layout

```text
project/
├─ main.py
├─ extractors.py
├─ filters.py
├─ excel_writer.py
├─ data/
│  └─ metadata/
│     ├─ screener_latest_results.html
│     ├─ screener_results_all.csv
│     └─ screener_results_filtered.xlsx
└─ README.md
```

## Run flow

A clean run should follow this order:

1. log in to Screener.[cite:630]
2. fetch `results/latest/?all=` with an optional date filter if needed.[cite:630]
3. parse company blocks and normalize the fields.[cite:630]
4. apply `market_cap > 500 Cr` filter.[cite:800][cite:802]
5. export the full CSV and filtered Excel outputs.[cite:800][cite:802]

## Practical takeaway

The current approach is already on the right path: use the latest-results page as the primary source, keep filtering reusable, and separate scraping, parsing, filtering, and Excel-writing into smaller modules. The outputs prove that market-cap parsing and filtered export are already working, while the HTML snapshot shows enough structure to support cleaner modular extraction next.[cite:630][cite:800][cite:802]
