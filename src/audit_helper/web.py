"""Web app for mobile upload of documents/images for OCR -> Excel/Zoho export."""
import os
import uuid
import shutil
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file

from .ocr import prepare_images, extract_entries
from .excel import write_csv, write_full_workbook
from .zoho_formats import FORMATS, FORMAT_LABELS, write as write_zoho_format, write_all as write_zoho_all
from .db import get_session
from .models import CompanyProfile, Document, Transaction, Verification
from .verify import verify_all
from .taccounts import make_postings, validate_balance

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
UPLOAD_ROOT = Path(os.getenv("UPLOAD_DIR", "/tmp/opencode/audit_uploads"))
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder=str(TEMPLATE_DIR))
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


def _load_profile(session, name="default"):
    from sqlmodel import select
    prof = session.exec(select(CompanyProfile).where(CompanyProfile.name == name)).first()
    if prof is None:
        prof = CompanyProfile(name=name)
        session.add(prof)
        session.commit()
        session.refresh(prof)
    return prof


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/scan", methods=["POST"])
def scan():
    files = request.files.getlist("files")
    fmt = request.form.get("format", "expenses")
    if fmt not in list(FORMATS.keys()) + ["all"]:
        fmt = "expenses"
    company = request.form.get("company", "default")
    if not files:
        return jsonify({"error": "No files uploaded."}), 400

    job_id = uuid.uuid4().hex
    job_dir = UPLOAD_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for f in files:
        if not f or not f.filename:
            continue
        dest = job_dir / f.filename
        f.save(str(dest))
        saved_paths.append(str(dest))

    if not saved_paths:
        return jsonify({"error": "No valid files."}), 400

    session = get_session(company)
    prof = _load_profile(session, company)
    pdict = {
        "authorized_spenders": prof.spenders_list(),
        "owners": prof.owners_list(),
        "cards": prof.cards_list(),
        "equity_mode": prof.equity_mode,
    }

    all_images = []
    for p in saved_paths:
        try:
            all_images.extend(prepare_images(p))
        except Exception as e:
            return jsonify({"error": f"Unsupported file {p}: {e}"}), 400

    try:
        ollama_url = request.form.get("ollama_url", "").strip() or None
        entries = extract_entries(all_images, base_url=ollama_url)
    except Exception as e:
        return jsonify({"error": f"OCR failed: {e}"}), 500

    verified = verify_all(entries, pdict)
    for e in verified:
        e["_source"] = ""

    flagged = [e for e in verified if e.get("classification") in ("personal", "unknown")]
    postings = make_postings(verified, pdict)

    # persist
    doc = Document(filename=", ".join(Path(p).name for p in saved_paths), entry_count=len(verified))
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
            currency=e.get("currency") or "USD",
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
        ver = Verification(transaction_id=txn.id, original_classification=e.get("classification", "unknown"))
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

    # delete raw uploaded files after extraction
    for p in saved_paths:
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass
    # clean temp pdf pages
    for p in saved_paths:
        pages_dir = Path(p).parent / ".audit_pages"
        if pages_dir.exists():
            shutil.rmtree(pages_dir, ignore_errors=True)

    out_dir = job_dir / "output"
    out_dir.mkdir(exist_ok=True)
    base = "audit"
    xlsx = out_dir / f"{base}.xlsx"
    csvp = out_dir / f"{base}.csv"

    write_full_workbook(verified, postings, flagged, v_rows, str(xlsx))
    write_csv(verified, str(csvp))

    if fmt == "all":
        zip_path = Path(write_zoho_all(verified, str(out_dir), base))
        downloads = [
            {"label": "Download Excel (.xlsx)", "url": f"/download/{job_id}/audit.xlsx"},
            {"label": "Download CSV", "url": f"/download/{job_id}/audit.csv"},
            {"label": "Download ALL Zoho formats (zip)", "url": f"/download/{job_id}/{zip_path.name}"},
        ]
    else:
        zoho = out_dir / f"{base}_zoho_{fmt}.csv"
        write_zoho_format(fmt, verified, str(zoho))
        downloads = [
            {"label": "Download Excel (.xlsx)", "url": f"/download/{job_id}/audit.xlsx"},
            {"label": "Download CSV", "url": f"/download/{job_id}/audit.csv"},
            {"label": f"Download Zoho {FORMAT_LABELS.get(fmt, fmt)} CSV", "url": f"/download/{job_id}/audit_zoho_{fmt}.csv"},
        ]

    return jsonify({
        "count": len(verified),
        "entries": verified,
        "balanced": validate_balance(postings),
        "downloads": downloads,
    })


@app.route("/download/<job_id>/<filename>")
def download(job_id, filename):
    safe = Path(filename).name
    path = UPLOAD_ROOT / job_id / "output" / safe
    if not path.exists():
        return jsonify({"error": "File not found."}), 404
    return send_file(str(path), as_attachment=True)


def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
