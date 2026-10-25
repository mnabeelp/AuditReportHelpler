"""Command-line interface for Audit Report Helper."""
import argparse
import json
import sys
from pathlib import Path

from .ocr import prepare_images, extract_entries, ocr_text
from .excel import write_excel, write_csv
from .zoho import write_zoho_csv
from .zoho_formats import FORMATS, FORMAT_LABELS, write as write_zoho_format, write_all as write_zoho_all


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

    write_excel(entries, str(xlsx))
    write_csv(entries, str(csvp))

    fmt = getattr(args, "zoho_format", "expenses")
    if fmt == "all":
        zip_path = write_zoho_all(entries, str(out_dir), base)
        print(f"Excel  -> {xlsx}")
        print(f"CSV    -> {csvp}")
        print(f"Zoho   -> {zip_path} (all formats)")
    else:
        zoho = out_dir / f"{base}_zoho_{fmt}.csv"
        write_zoho_format(fmt, entries, str(zoho))
        print(f"Excel  -> {xlsx}")
        print(f"CSV    -> {csvp}")
        print(f"Zoho ({FORMAT_LABELS.get(fmt, fmt)}) -> {zoho}")

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
    scan.add_argument("--format", dest="zoho_format", default="expenses",
                      choices=list(FORMATS.keys()) + ["all"],
                      help="Zoho Books import format (or \"all\" for a zip of every format).")
    scan.set_defaults(func=cmd_scan)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
