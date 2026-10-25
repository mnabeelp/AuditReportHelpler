"""Transaction verification against company profile."""
import json
import re
from typing import List, Dict

SALARY_KEYWORDS = re.compile(r"salary|wages|payroll|compensation|stipend", re.I)
CAPITAL_KEYWORDS = re.compile(r"capital contribution|owner investment|funding|equity injection", re.I)
DRAW_KEYWORDS = re.compile(r"owner draw|drawing|withdrawal by owner|personal withdrawal", re.I)
INVESTOR_KEYWORDS = re.compile(r"investor|seed funding|series [a-z]", re.I)


def classify_transaction(txn: dict, profile: dict) -> str:
    """Return one of: company, personal, owner, unknown."""
    holder = (txn.get("account_holder_name") or "").strip().lower()
    spenders = [s.lower() for s in profile.get("authorized_spenders", [])]
    owners = [o["name"].lower() for o in profile.get("owners", [])]
    desc = (txn.get("description") or "") + " " + (txn.get("notes") or "")

    # owner takes precedence
    if holder and holder in owners:
        return "owner"
    if any(k in desc.lower() for k in ["owner draw", "capital contribution", "investor funding"]):
        # only if holder is an owner or unknown holder
        if holder in owners or not holder:
            return "owner"

    if holder:
        if holder in spenders:
            return "company"
        # holder present but not authorized -> personal (known employee not authorized) or unknown
        return "personal" if holder else "unknown"

    # no holder name: heuristic by description
    if SALARY_KEYWORDS.search(desc):
        return "company"
    return "unknown"


def detect_owner_type(txn: dict) -> str:
    desc = ((txn.get("description") or "") + " " + (txn.get("notes") or "")).lower()
    if CAPITAL_KEYWORDS.search(desc):
        return "capital"
    if DRAW_KEYWORDS.search(desc):
        return "draw"
    if INVESTOR_KEYWORDS.search(desc):
        return "investor_funding"
    if SALARY_KEYWORDS.search(desc):
        return "salary"
    return "draw"


def verify_all(transactions: List[dict], profile: dict) -> List[dict]:
    out = []
    for t in transactions:
        c = classify_transaction(t, profile)
        t = dict(t)
        t["classification"] = c
        if c == "owner":
            t["owner_type"] = detect_owner_type(t)
        out.append(t)
    return out
