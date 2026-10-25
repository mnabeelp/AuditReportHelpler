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


POSTING_COLUMNS = [
    "Date", "Account", "Debit", "Credit", "Offset Account",
    "Description", "Reference", "Vendor", "Classification",
]

FLAGGED_COLUMNS = [
    "Date", "Vendor", "Doc Number", "Description", "Account", "Amount",
    "Currency", "Classification", "Reason", "Account Holder",
]

OWNER_COLUMNS = [
    "Date", "Owner", "Type", "Account", "Debit", "Credit", "Description", "Reference",
]

VERIFY_LOG_COLUMNS = [
    "Transaction ID", "Date", "Vendor", "Description", "Amount",
    "Original Classification", "Effective Classification", "Overridden", "Note",
]


def write_full_workbook(
    entries: list[dict],
    postings: list[dict],
    flagged: list[dict],
    verifications: list[dict],
    output_path: str,
) -> str:
    """Write a comprehensive workbook with all audit sheets."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()

    # --- Audit Entries (classified) ---
    ws = wb.active
    ws.title = "Audit Entries"
    cols = COLUMNS  # reuse
    hdr_fill = PatternFill("solid", fgColor="1F4E79")
    hdr_font = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for c, col in enumerate(cols, start=1):
        cell = ws.cell(row=1, column=c, value=col)
        cell.fill = hdr_fill; cell.font = hdr_font; cell.border = border
    for r, e in enumerate(entries, start=2):
        row = _normalize(e, e.get("_source", ""))
        row["Classification"] = e.get("classification")
        for c, col in enumerate(cols, start=1):
            v = row.get(col)
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = border
            if col in ("Amount", "Tax"):
                cell.number_format = "#,##0.00"

    # --- T-Accounts ---
    wst = wb.create_sheet("T-Accounts")
    for c, col in enumerate(POSTING_COLUMNS, start=1):
        cell = wst.cell(row=1, column=c, value=col)
        cell.fill = hdr_fill; cell.font = hdr_font; cell.border = border
    for r, p in enumerate(postings, start=2):
        vals = [p.get("date"), p.get("account"), p.get("debit", 0), p.get("credit", 0),
                p.get("offset_account"), p.get("description"), p.get("reference"),
                p.get("vendor"), p.get("classification")]
        for c, v in enumerate(vals, start=1):
            cell = wst.cell(row=r, column=c, value=v)
            cell.border = border
            if c in (3, 4):
                cell.number_format = "#,##0.00"

    # --- Flagged Transactions ---
    wsf = wb.create_sheet("Flagged")
    for c, col in enumerate(FLAGGED_COLUMNS, start=1):
        cell = wsf.cell(row=1, column=c, value=col)
        cell.fill = PatternFill("solid", fgColor="C00000"); cell.font = hdr_font; cell.border = border
    for r, f in enumerate(flagged, start=2):
        vals = [f.get("date"), f.get("vendor"), f.get("doc_number"), f.get("description"),
                f.get("account"), f.get("amount"), f.get("currency"), f.get("classification"),
                f.get("reason", ""), f.get("account_holder_name")]
        for c, v in enumerate(vals, start=1):
            cell = wsf.cell(row=r, column=c, value=v)
            cell.border = border
            if c == 6:
                cell.number_format = "#,##0.00"

    # --- Owner / Investor Activity ---
    wso = wb.create_sheet("Owner Activity")
    for c, col in enumerate(OWNER_COLUMNS, start=1):
        cell = wso.cell(row=1, column=c, value=col)
        cell.fill = PatternFill("solid", fgColor="7F6000"); cell.font = hdr_font; cell.border = border
    owner_rows = [p for p in postings if p.get("classification") == "owner"]
    for r, p in enumerate(owner_rows, start=2):
        vals = [p.get("date"), p.get("vendor"), p.get("owner_type"), p.get("account"),
                p.get("debit", 0), p.get("credit", 0), p.get("description"), p.get("reference")]
        for c, v in enumerate(vals, start=1):
            cell = wso.cell(row=r, column=c, value=v)
            cell.border = border
            if c in (5, 6):
                cell.number_format = "#,##0.00"

    # --- Verification Log ---
    wsv = wb.create_sheet("Verification Log")
    for c, col in enumerate(VERIFY_LOG_COLUMNS, start=1):
        cell = wsv.cell(row=1, column=c, value=col)
        cell.fill = hdr_fill; cell.font = hdr_font; cell.border = border
    for r, v in enumerate(verifications, start=2):
        vals = [v.get("transaction_id"), v.get("date"), v.get("vendor"), v.get("description"),
                v.get("amount"), v.get("original"), v.get("effective"),
                "Yes" if v.get("overridden") else "No", v.get("note")]
        for c, val in enumerate(vals, start=1):
            cell = wsv.cell(row=r, column=c, value=val)
            cell.border = border
            if c == 5:
                cell.number_format = "#,##0.00"

    # --- Summary ---
    summary = wb.create_sheet("Summary")
    summary["A1"] = "Audit Report Summary"; summary["A1"].font = Font(bold=True, size=14)
    summary["A3"] = "Total entries"; summary["B3"] = len(entries)
    summary["A4"] = "Total postings"; summary["B4"] = len(postings)
    summary["A5"] = "Flagged"; summary["B5"] = len(flagged)
    summary["A6"] = "Owner postings"; summary["B6"] = len(owner_rows)
    td = sum(p.get("debit") or 0 for p in postings)
    tc = sum(p.get("credit") or 0 for p in postings)
    summary["A7"] = "Total debits"; summary["B7"] = td; summary["B7"].number_format = "#,##0.00"
    summary["A8"] = "Total credits"; summary["B8"] = tc; summary["B8"].number_format = "#,##0.00"
    summary["A9"] = "Balanced"; summary["B9"] = abs(td - tc) < 0.005

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(out))
    return str(out)
