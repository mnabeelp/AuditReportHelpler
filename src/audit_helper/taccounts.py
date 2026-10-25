"""T-account (double-entry) posting generation."""
from typing import List, Dict

BANK_ACCOUNT = "Bank"


def _owner_account_name(profile: dict, owner_name: str, kind: str) -> str:
    equity_mode = profile.get("equity_mode", "single")
    base = {
        "capital": "Owner's Capital",
        "draw": "Owner's Drawings",
        "investor_funding": "Investor Funding",
        "salary": "Salary Expense",
    }[kind]
    if equity_mode == "multi" and owner_name:
        return f"{owner_name} - {base}"
    return base


def make_postings(transactions: List[dict], profile: dict) -> List[dict]:
    """Return list of posting dicts: date, account, debit, credit, offset, description, reference, classification."""
    postings = []
    for t in transactions:
        cls = t.get("classification")
        if cls not in ("company", "owner"):
            continue
        amt = t.get("amount") or 0
        tax = t.get("tax") or 0
        total = amt + tax
        date = t.get("date")
        desc = t.get("description")
        ref = t.get("doc_number")
        vendor = t.get("vendor")
        account = t.get("account") or "Uncategorized"
        paid_through = t.get("paid_through") or BANK_ACCOUNT

        if cls == "company":
            # Expense/income entry: debit expense account, credit bank (or paid_through)
            postings.append({
                "date": date, "account": account, "debit": total, "credit": 0,
                "offset_account": paid_through, "description": desc, "reference": ref,
                "classification": "company", "vendor": vendor,
            })
            postings.append({
                "date": date, "account": paid_through, "debit": 0, "credit": total,
                "offset_account": account, "description": desc, "reference": ref,
                "classification": "company", "vendor": vendor,
            })
        elif cls == "owner":
            owner_name = t.get("account_holder_name") or ""
            otype = t.get("owner_type", "draw")
            equity_acct = _owner_account_name(profile, owner_name, otype)
            if otype in ("capital", "investor_funding"):
                # debit bank, credit equity
                postings.append({
                    "date": date, "account": paid_through, "debit": total, "credit": 0,
                    "offset_account": equity_acct, "description": desc, "reference": ref,
                    "classification": "owner", "vendor": vendor, "owner_type": otype,
                })
                postings.append({
                    "date": date, "account": equity_acct, "debit": 0, "credit": total,
                    "offset_account": paid_through, "description": desc, "reference": ref,
                    "classification": "owner", "vendor": vendor, "owner_type": otype,
                })
            elif otype == "salary":
                # salary expense
                postings.append({
                    "date": date, "account": "Salary Expense", "debit": total, "credit": 0,
                    "offset_account": paid_through, "description": desc, "reference": ref,
                    "classification": "owner", "vendor": vendor, "owner_type": otype,
                })
                postings.append({
                    "date": date, "account": paid_through, "debit": 0, "credit": total,
                    "offset_account": "Salary Expense", "description": desc, "reference": ref,
                    "classification": "owner", "vendor": vendor, "owner_type": otype,
                })
            else:  # draw
                postings.append({
                    "date": date, "account": equity_acct, "debit": total, "credit": 0,
                    "offset_account": paid_through, "description": desc, "reference": ref,
                    "classification": "owner", "vendor": vendor, "owner_type": otype,
                })
                postings.append({
                    "date": date, "account": paid_through, "debit": 0, "credit": total,
                    "offset_account": equity_acct, "description": desc, "reference": ref,
                    "classification": "owner", "vendor": vendor, "owner_type": otype,
                })
    return postings


def validate_balance(postings: List[dict]) -> bool:
    total_d = sum(p.get("debit") or 0 for p in postings)
    total_c = sum(p.get("credit") or 0 for p in postings)
    return abs(total_d - total_c) < 0.005
