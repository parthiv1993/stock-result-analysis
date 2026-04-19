from pathlib import Path
import csv

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.table import Table, TableStyleInfo


HEADERS = [
    "company_name",
    "screener_url",
    "result_pdf_link",
    "price",
    "market_cap_text",
    "market_cap_cr",
    "pe",
    "sales_latest_qtr_cr",
    "sales_yoy_pct",
    "net_profit_latest_qtr_cr",
    "net_profit_yoy_pct",
]

DISPLAY_HEADERS = [
    "Company Name",
    "Screener URL",
    "Result PDF Link",
    "Price",
    "Market Cap",
    "Market Cap (Cr)",
    "PE",
    "Sales Latest Qtr (Cr)",
    "Sales YoY (%)",
    "Net Profit Latest Qtr (Cr)",
    "Net Profit YoY (%)",
]


HDR_FILL = PatternFill("solid", fgColor="1F4E78")
HDR_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
BODY_FONT = Font(name="Calibri", size=11, color="000000")
LINK_FONT = Font(name="Calibri", size=11, color="0000FF", underline="single")

LEFT = Alignment(horizontal="left", vertical="center")
RIGHT = Alignment(horizontal="right", vertical="center")
CENTER = Alignment(horizontal="center", vertical="center")


def write_csv(rows, path):
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_excel(rows, path):
    path = Path(path)

    wb = Workbook()
    ws = wb.active
    ws.title = "Results"

    ws.append(DISPLAY_HEADERS)

    for row in rows:
        ws.append([
            row.get("company_name", ""),
            row.get("screener_url", ""),
            row.get("result_pdf_link", ""),
            row.get("price", ""),
            row.get("market_cap_text", ""),
            row.get("market_cap_cr", ""),
            row.get("pe", ""),
            row.get("sales_latest_qtr_cr", ""),
            row.get("sales_yoy_pct", ""),
            row.get("net_profit_latest_qtr_cr", ""),
            row.get("net_profit_yoy_pct", ""),
        ])

    for cell in ws[1]:
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.alignment = CENTER

    for r in range(2, ws.max_row + 1):
        ws.cell(r, 1).font = BODY_FONT
        ws.cell(r, 1).alignment = LEFT

        ws.cell(r, 2).font = LINK_FONT
        ws.cell(r, 2).alignment = LEFT
        if ws.cell(r, 2).value:
            ws.cell(r, 2).hyperlink = ws.cell(r, 2).value

        ws.cell(r, 3).font = LINK_FONT
        ws.cell(r, 3).alignment = LEFT
        if ws.cell(r, 3).value:
            ws.cell(r, 3).hyperlink = ws.cell(r, 3).value

        for c in [4, 5, 6, 7, 8, 9, 10, 11]:
            ws.cell(r, c).font = BODY_FONT
            ws.cell(r, c).alignment = RIGHT

        ws.cell(r, 4).number_format = '#,##0.00'
        ws.cell(r, 6).number_format = '#,##0.00'
        ws.cell(r, 7).number_format = '#,##0.00'
        ws.cell(r, 8).number_format = '#,##0.00'
        ws.cell(r, 9).number_format =  '#,##0.00'
        ws.cell(r, 10).number_format = '#,##0.00'
        ws.cell(r, 11).number_format =  '#,##0.00'

    widths = {
        "A": 28,
        "B": 42,
        "C": 42,
        "D": 12,
        "E": 18,
        "F": 16,
        "G": 10,
        "H": 20,
        "I": 14,
        "J": 24,
        "K": 16,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    ws.freeze_panes = "A2"

    if ws.max_row >= 2:
        table = Table(displayName="ResultsTable", ref=f"A1:K{ws.max_row}")
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