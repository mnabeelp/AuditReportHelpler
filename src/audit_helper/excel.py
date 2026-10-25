"""Write extracted entries into an Excel workbook."""
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

COLUMNS = [
    "Date",
    "Vendor",
    "Doc Number",
    "Description",
    "Account",
    "Amount",
    "Tax",
    "Currency",
    "Payment Mode",
    "Paid Through",
    "Notes",
    "Source File",
]


def _normalize(entry: dict, source: str = "") -> dict:
    return {
        "Date": entry.get("date"),
        "Vendor": entry.get("vendor"),
        "Doc Number": entry.get("doc_number"),
        "Description": entry.get("description"),
        "Account": entry.get("account"),
        "Amount": entry.get("amount"),
        "Tax": entry.get("tax", 0),
        "Currency": entry.get("currency") or "USD",
        "Payment Mode": entry.get("payment_mode"),
        "Paid Through": entry.get("paid_through"),
        "Notes": entry.get("notes"),
        "Source File": source,
    }


def write_excel(entries: list[dict], output_path: str, source_files: list[str] | None = None) -> str:
    """Write entries to an .xlsx file with formatting. Returns output path."""
    src_map = {}
    if source_files:
        # best-effort: assign source by index group; default empty
        pass

    rows = [_normalize(e, "") for e in entries]

    wb = Workbook()
    ws = wb.active
    ws.title = "Audit Entries"

    # Header
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for c, col in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=c, value=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    for r, row in enumerate(rows, start=2):
        for c, col in enumerate(COLUMNS, start=1):
            val = row[col]
            cell = ws.cell(row=r, column=c, value=val)
            cell.border = border
            if col in ("Amount", "Tax"):
                cell.number_format = "#,##0.00"
            if col == "Date" and val:
                cell.number_format = "yyyy-mm-dd"

    # Column widths
    widths = {
        "Date": 12, "Vendor": 22, "Doc Number": 16, "Description": 34,
        "Account": 20, "Amount": 12, "Tax": 10, "Currency": 9,
        "Payment Mode": 12, "Paid Through": 16, "Notes": 30, "Source File": 24,
    }
    for c, col in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(c)].width = widths.get(col, 14)

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{len(rows) + 1}"

    # Summary sheet
    summary = wb.create_sheet("Summary")
    summary["A1"] = "Audit Report Summary"
    summary["A1"].font = Font(bold=True, size=14)
    summary["A3"] = "Generated"
    summary["B3"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary["A4"] = "Total entries"
    summary["B4"] = len(rows)
    total_amt = sum((r.get("Amount") or 0) for r in rows)
    total_tax = sum((r.get("Tax") or 0) for r in rows)
    summary["A5"] = "Total amount"
    summary["B5"] = total_amt
    summary["B5"].number_format = "#,##0.00"
    summary["A6"] = "Total tax"
    summary["B6"] = total_tax
    summary["B6"].number_format = "#,##0.00"
    # by account
    from collections import defaultdict
    by_acct = defaultdict(float)
    for r in rows:
        by_acct[r.get("Account") or "(uncategorized)"] += (r.get("Amount") or 0)
    rr = 8
    summary.cell(row=rr, column=1, value="By Account").font = Font(bold=True)
    rr += 1
    for acct, amt in sorted(by_acct.items()):
        summary.cell(row=rr, column=1, value=acct)
        summary.cell(row=rr, column=2, value=amt).number_format = "#,##0.00"
        rr += 1

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(out))
    return str(out)


def write_csv(entries: list[dict], output_path: str) -> str:
    """Write entries to CSV (generic)."""
    rows = [_normalize(e, "") for e in entries]
    df = pd.DataFrame(rows, columns=COLUMNS)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return str(out)
