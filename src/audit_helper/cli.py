"""Command-line interface for Audit Report Helper."""
import argparse
import json
import sys
from pathlib import Path

from .ocr import prepare_images, extract_entries, ocr_text
from .excel import write_excel, write_csv
from .zoho import write_zoho_csv


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

    base = Path(input_path).stem
    xlsx = out_dir / f"{base}_audit.xlsx"
    csvp = out_dir / f"{base}_audit.csv"
    zoho = out_dir / f"{base}_zoho.csv"

    write_excel(entries, str(xlsx))
    write_csv(entries, str(csvp))
    write_zoho_csv(entries, str(zoho))

    print(f"Excel  -> {xlsx}")
    print(f"CSV    -> {csvp}")
    print(f"Zoho   -> {zoho}")

    if args.dump_json:
        print(json.dumps(entries, indent=2, ensure_ascii=False))


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
    scan.set_defaults(func=cmd_scan)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
