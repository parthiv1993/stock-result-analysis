import csv

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.table import Table, TableStyleInfo


FIELDNAMES = [
    "company_name",
    "company_url",
    "pdf_url",
    "price",
    "market_cap_text",
    "market_cap_cr",
    "pe",
    "sales_latest_qtr_cr",
    "sales_yoy_pct",
    "net_profit_latest_qtr_cr",
    "net_profit_yoy_pct",
]

HEADERS = [
    "Company Name",
    "Company URL",
    "PDF URL",
    "Price",
    "Market Cap",
    "Market Cap (Cr)",
    "PE",
    "Sales Latest Qtr (Cr)",
    "Sales YoY (%)",
    "Net Profit Latest Qtr (Cr)",
    "Net Profit YoY (%)",
]


def write_csv(rows, path):
    if not rows:
        return

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_excel(rows, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Filtered Results"

    ws.append(HEADERS)

    for row in rows:
        ws.append([
            row.get("company_name"),
            row.get("company_url"),
            row.get("pdf_url"),
            row.get("price"),
            row.get("market_cap_text"),
            row.get("market_cap_cr"),
            row.get("pe"),
            row.get("sales_latest_qtr_cr"),
            row.get("sales_yoy_pct"),
            row.get("net_profit_latest_qtr_cr"),
            row.get("net_profit_yoy_pct"),
        ])

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True, name="Calibri")
    body_font = Font(name="Calibri")
    link_font = Font(name="Calibri", color="0000EE", underline="single")
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center")
    right = Alignment(horizontal="right", vertical="center")

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center

    for row_idx in range(2, ws.max_row + 1):
        for col_idx in range(1, ws.max_column + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = body_font
            cell.alignment = left if col_idx in (1, 2, 3, 5) else right

        for col_idx in (2, 3):
            cell = ws.cell(row=row_idx, column=col_idx)
            if cell.value:
                cell.hyperlink = cell.value
                cell.font = link_font
                cell.alignment = left

    widths = {
        "A": 28, "B": 42, "C": 42, "D": 12, "E": 16,
        "F": 16, "G": 10, "H": 20, "I": 14, "J": 23, "K": 18
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    ws.freeze_panes = "A2"

    if ws.max_row > 1:
        table = Table(displayName="FilteredResults", ref=f"A1:K{ws.max_row}")
        style = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )
        table.tableStyleInfo = style
        ws.add_table(table)

    wb.save(path)