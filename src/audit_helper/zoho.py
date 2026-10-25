"""Export entries to a Zoho Books compatible CSV."""
from pathlib import Path

import pandas as pd

# Zoho Books "Expenses" import template columns.
ZOHO_COLUMNS = [
    "Date",
    "Account",
    "Amount",
    "Tax",
    "Is Inclusive Tax",
    "Vendor",
    "Reference#",
    "Description",
    "Currency Code",
    "Exchange Rate",
    "Paid Through",
    "Payment Mode",
    "Notes",
]


def to_zoho_rows(entries: list[dict]) -> list[dict]:
    rows = []
    for e in entries:
        rows.append({
            "Date": e.get("date"),
            "Account": e.get("account"),
            "Amount": e.get("amount"),
            "Tax": e.get("tax", 0),
            "Is Inclusive Tax": "FALSE",
            "Vendor": e.get("vendor"),
            "Reference#": e.get("doc_number"),
            "Description": e.get("description"),
            "Currency Code": e.get("currency") or "USD",
            "Exchange Rate": 1,
            "Paid Through": e.get("paid_through"),
            "Payment Mode": e.get("payment_mode"),
            "Notes": e.get("notes"),
        })
    return rows


def write_zoho_csv(entries: list[dict], output_path: str) -> str:
    rows = to_zoho_rows(entries)
    df = pd.DataFrame(rows, columns=ZOHO_COLUMNS)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return str(out)
