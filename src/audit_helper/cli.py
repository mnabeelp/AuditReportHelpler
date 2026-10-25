"""Command-line interface for Audit Report Helper."""
import argparse
import json
import os
import shutil
from pathlib import Path

from .config import DEFAULT_CURRENCY
from .ocr import prepare_images, extract_entries, ocr_text
from .excel import write_excel, write_csv, write_full_workbook
from .zoho import write_zoho_csv
from .zoho_formats import FORMATS, FORMAT_LABELS, write as write_zoho_format, write_all as write_zoho_all
from .db import get_session, get_engine
from .models import CompanyProfile, Document, Transaction, Verification, Export
from .verify import verify_all
from .taccounts import make_postings, validate_balance

SQLModel = None
try:
    from sqlmodel import SQLModel as _SM
    SQLModel = _SM
except Exception:
    pass


def _load_profile(session, name="default"):
    from sqlmodel import select
    prof = session.exec(select(CompanyProfile).where(CompanyProfile.name == name)).first()
    if prof is None:
        prof = CompanyProfile(name=name)
        session.add(prof)
        session.commit()
        session.refresh(prof)
    return prof


def _profile_dict(prof):
    import json
    return {
        "authorized_spenders": prof.spenders_list(),
        "owners": prof.owners_list(),
        "cards": prof.cards_list(),
        "equity_mode": prof.equity_mode,
    }


def cmd_scan(args):
    input_path = args.input
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    images = prepare_images(input_path)
    print(f"Prepared {len(images)} image(s) for OCR.")

    if args.text_only:
        text = ocr_text(images)
        out_txt = out_dir / (Path(input_path).stem + "_ocr.txt")
        out_txt.write_text(text, encoding="utf-8")
        print(f"OCR text saved to {out_txt}")
        return

    entries = extract_entries(images)
    print(f"Extracted {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}.")

    if not entries:
        print("No entries extracted. Try --text-only for raw OCR output.")
        return

    company = getattr(args, "company", "default")
    session = get_session(company)
    prof = _load_profile(session, company)
    pdict = _profile_dict(prof)

    # verify
    verified = verify_all(entries, pdict)
    for e in verified:
        e.setdefault("_source", Path(input_path).name)

    # flagged = personal/unknown
    flagged = [e for e in verified if e.get("classification") in ("personal", "unknown")]

    # postings
    postings = make_postings(verified, pdict)
    balanced = validate_balance(postings)
    print(f"Postings: {len(postings)} (balanced: {balanced})")

    # persist to DB (immutable)
    doc = Document(filename=Path(input_path).name, entry_count=len(verified))
    session.add(doc)
    session.commit()
    session.refresh(doc)

    v_rows = []
    for e in verified:
        txn = Transaction(
            document_id=doc.id,
            date=e.get("date"),
            vendor=e.get("vendor"),
            doc_number=e.get("doc_number"),
            description=e.get("description"),
            account=e.get("account"),
            amount=e.get("amount"),
            tax=e.get("tax", 0),
            currency=e.get("currency") or DEFAULT_CURRENCY,
            payment_mode=e.get("payment_mode"),
            paid_through=e.get("paid_through"),
            notes=e.get("notes"),
            account_holder_name=e.get("account_holder_name"),
            card_last4=e.get("card_last4"),
            classification=e.get("classification", "unknown"),
        )
        session.add(txn)
        session.commit()
        session.refresh(txn)
        ver = Verification(
            transaction_id=txn.id,
            original_classification=e.get("classification", "unknown"),
        )
        session.add(ver)
        v_rows.append({
            "transaction_id": txn.id,
            "date": e.get("date"),
            "vendor": e.get("vendor"),
            "description": e.get("description"),
            "amount": e.get("amount"),
            "original": e.get("classification", "unknown"),
            "effective": e.get("classification", "unknown"),
            "overridden": False,
            "note": None,
        })
    session.commit()

    # delete raw uploaded file? CLI input is user's file; don't delete user's original.
    # (Web app deletes after extraction.)

    base = Path(input_path).stem
    xlsx = out_dir / f"{base}_audit.xlsx"
    csvp = out_dir / f"{base}_audit.csv"

    write_full_workbook(verified, postings, flagged, v_rows, str(xlsx))
    write_csv(verified, str(csvp)) if False else None

    # generic csv of entries
    from .excel import write_csv as _wc
    _wc(verified, str(csvp))

    fmt = getattr(args, "zoho_format", "expenses")
    if fmt == "all":
        zip_path = write_zoho_all(verified, str(out_dir), base)
        print(f"Excel  -> {xlsx}")
        print(f"CSV    -> {csvp}")
        print(f"Zoho   -> {zip_path} (all formats)")
    else:
        zoho = out_dir / f"{base}_zoho_{fmt}.csv"
        write_zoho_format(fmt, verified, str(zoho))
        print(f"Excel  -> {xlsx}")
        print(f"CSV    -> {csvp}")
        print(f"Zoho ({FORMAT_LABELS.get(fmt, fmt)}) -> {zoho}")

    if args.dump_json:
        print(json.dumps(verified, indent=2, ensure_ascii=False, default=str))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="audit-helper",
        description="Audit Report Helper: OCR documents/images -> Excel table -> bookkeeping export (Zoho).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="Scan a document/image/PDF and produce exports.")
    scan.add_argument("input", help="Path to image or PDF file.")
    scan.add_argument("-o", "--output-dir", default="./output", help="Output directory.")
    scan.add_argument("--text-only", action="store_true", help="Only produce raw OCR text.")
    scan.add_argument("--dump-json", action="store_true", help="Print extracted JSON to stdout.")
    scan.add_argument("--company", default="default", help="Company profile name.")
    scan.add_argument("--format", dest="zoho_format", default="expenses",
                      choices=list(FORMATS.keys()) + ["all"],
                      help="Zoho Books import format (or 'all' for a zip of every format).")
    scan.add_argument("--mode", default="both", choices=["entries", "taccounts", "both"],
                      help="Output mode.")
    scan.set_defaults(func=cmd_scan)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
