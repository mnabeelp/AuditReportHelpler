"""Multiple Zoho Books import formats (CSV templates)."""
from pathlib import Path
import zipfile

import pandas as pd


def _g(e, key, default=None):
    return e.get(key) if e.get(key) is not None else default


# --- Column definitions per Zoho Books import template (simplified) ---

EXPENSES_COLUMNS = [
    "Date", "Account", "Amount", "Tax", "Is Inclusive Tax", "Vendor",
    "Reference#", "Description", "Currency Code", "Exchange Rate",
    "Paid Through", "Payment Mode", "Notes",
]

BILLS_COLUMNS = [
    "Bill Number", "Vendor Name", "Bill Date", "Due Date", "Currency Code",
    "Exchange Rate", "Item Name", "Account", "Description", "Quantity", "Rate",
    "Amount", "Tax", "Tax Type", "Notes",
]

INVOICES_COLUMNS = [
    "Invoice Number", "Customer Name", "Invoice Date", "Due Date", "Currency Code",
    "Exchange Rate", "Item Name", "Description", "Quantity", "Rate", "Amount",
    "Tax", "Tax Type", "Notes",
]

JOURNALS_COLUMNS = [
    "Journal Date", "Journal Number", "Notes", "Currency Code", "Account",
    "Debit", "Credit", "Description",
]

BANK_COLUMNS = [
    "Date", "Account", "Amount", "Payee", "Description", "Reference#",
    "Currency Code", "Transaction Type", "Notes",
]

PURCHASE_ORDERS_COLUMNS = [
    "Purchase Order Number", "Vendor Name", "Date", "Delivery Date",
    "Currency Code", "Exchange Rate", "Item Name", "Description", "Quantity",
    "Rate", "Amount", "Tax", "Notes",
]

SALES_ORDERS_COLUMNS = [
    "Sales Order Number", "Customer Name", "Date", "Shipment Date",
    "Currency Code", "Exchange Rate", "Item Name", "Description", "Quantity",
    "Rate", "Amount", "Tax", "Notes",
]

FORMATS = {
    "expenses": EXPENSES_COLUMNS,
    "bills": BILLS_COLUMNS,
    "invoices": INVOICES_COLUMNS,
    "journals": JOURNALS_COLUMNS,
    "bank": BANK_COLUMNS,
    "purchase_orders": PURCHASE_ORDERS_COLUMNS,
    "sales_orders": SALES_ORDERS_COLUMNS,
}

FORMAT_LABELS = {
    "expenses": "Expenses",
    "bills": "Bills",
    "invoices": "Invoices",
    "journals": "Journals",
    "bank": "Bank Transactions",
    "purchase_orders": "Purchase Orders",
    "sales_orders": "Sales Orders",
}


def _amount(e):
    return e.get("amount")


def to_rows(fmt: str, entries: list[dict]) -> list[dict]:
    rows = []
    for e in entries:
        amt = _amount(e) or 0
        tax = e.get("tax", 0) or 0
        cur = e.get("currency") or "USD"
        if fmt == "expenses":
            rows.append({
                "Date": e.get("date"),
                "Account": e.get("account"),
                "Amount": amt,
                "Tax": tax,
                "Is Inclusive Tax": "FALSE",
                "Vendor": e.get("vendor"),
                "Reference#": e.get("doc_number"),
                "Description": e.get("description"),
                "Currency Code": cur,
                "Exchange Rate": 1,
                "Paid Through": e.get("paid_through"),
                "Payment Mode": e.get("payment_mode"),
                "Notes": e.get("notes"),
            })
        elif fmt == "bills":
            rows.append({
                "Bill Number": e.get("doc_number"),
                "Vendor Name": e.get("vendor"),
                "Bill Date": e.get("date"),
                "Due Date": None,
                "Currency Code": cur,
                "Exchange Rate": 1,
                "Item Name": e.get("description"),
                "Account": e.get("account"),
                "Description": e.get("description"),
                "Quantity": 1,
                "Rate": amt,
                "Amount": amt,
                "Tax": tax,
                "Tax Type": "Tax",
                "Notes": e.get("notes"),
            })
        elif fmt == "invoices":
            rows.append({
                "Invoice Number": e.get("doc_number"),
                "Customer Name": e.get("vendor"),
                "Invoice Date": e.get("date"),
                "Due Date": None,
                "Currency Code": cur,
                "Exchange Rate": 1,
                "Item Name": e.get("description"),
                "Description": e.get("description"),
                "Quantity": 1,
                "Rate": amt,
                "Amount": amt,
                "Tax": tax,
                "Tax Type": "Tax",
                "Notes": e.get("notes"),
            })
        elif fmt == "journals":
            # One debit line per entry (amount to account); balancing credit omitted (user completes).
            rows.append({
                "Journal Date": e.get("date"),
                "Journal Number": e.get("doc_number"),
                "Notes": e.get("notes"),
                "Currency Code": cur,
                "Account": e.get("account"),
                "Debit": amt,
                "Credit": 0,
                "Description": e.get("description"),
            })
        elif fmt == "bank":
            rows.append({
                "Date": e.get("date"),
                "Account": e.get("paid_through") or e.get("account"),
                "Amount": amt,
                "Payee": e.get("vendor"),
                "Description": e.get("description"),
                "Reference#": e.get("doc_number"),
                "Currency Code": cur,
                "Transaction Type": "Expense" if amt else "Deposit",
                "Notes": e.get("notes"),
            })
        elif fmt in ("purchase_orders", "sales_orders"):
            number_key = "Purchase Order Number" if fmt == "purchase_orders" else "Sales Order Number"
            party_key = "Vendor Name" if fmt == "purchase_orders" else "Customer Name"
            rows.append({
                number_key: e.get("doc_number"),
                party_key: e.get("vendor"),
                "Date": e.get("date"),
                "Delivery Date" if fmt == "purchase_orders" else "Shipment Date": None,
                "Currency Code": cur,
                "Exchange Rate": 1,
                "Item Name": e.get("description"),
                "Description": e.get("description"),
                "Quantity": 1,
                "Rate": amt,
                "Amount": amt,
                "Tax": tax,
                "Notes": e.get("notes"),
            })
        else:
            rows.append({"Notes": e.get("notes")})
    return rows


def write(fmt: str, entries: list[dict], output_path: str) -> str:
    rows = to_rows(fmt, entries)
    df = pd.DataFrame(rows, columns=FORMATS[fmt])
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return str(out)


def write_all(entries: list[dict], out_dir: str, prefix: str = "audit") -> str:
    """Write every Zoho format and zip them. Returns path to zip."""
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    files = []
    for fmt in FORMATS:
        p = d / f"{prefix}_{fmt}.csv"
        write(fmt, entries, str(p))
        files.append(p)
    zip_path = d / f"{prefix}_zoho_all.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, p.name)
    return str(zip_path)
