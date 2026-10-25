"""Web app for mobile upload of documents/images for OCR -> Excel/Zoho export."""
import os
import uuid
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file

from .ocr import prepare_images, extract_entries
from .excel import write_excel, write_csv
from .zoho import write_zoho_csv

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
UPLOAD_ROOT = Path(os.getenv("UPLOAD_DIR", "/tmp/opencode/audit_uploads"))
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder=str(TEMPLATE_DIR))
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/scan", methods=["POST"])
def scan():
    files = request.files.getlist("files")
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

    all_images = []
    for p in saved_paths:
        try:
            all_images.extend(prepare_images(p))
        except Exception as e:
            return jsonify({"error": f"Unsupported file {p}: {e}"}), 400

    try:
        entries = extract_entries(all_images)
    except Exception as e:
        return jsonify({"error": f"OCR failed: {e}"}), 500

    out_dir = job_dir / "output"
    out_dir.mkdir(exist_ok=True)
    base = "audit"
    xlsx = out_dir / f"{base}.xlsx"
    csvp = out_dir / f"{base}.csv"
    zoho = out_dir / f"{base}_zoho.csv"

    write_excel(entries, str(xlsx))
    write_csv(entries, str(csvp))
    write_zoho_csv(entries, str(zoho))

    downloads = [
        {"label": "Download Excel (.xlsx)", "url": f"/download/{job_id}/audit.xlsx"},
        {"label": "Download CSV", "url": f"/download/{job_id}/audit.csv"},
        {"label": "Download Zoho CSV", "url": f"/download/{job_id}/audit_zoho.csv"},
    ]

    return jsonify({
        "count": len(entries),
        "entries": entries,
        "downloads": downloads,
    })


@app.route("/download/<job_id>/<filename>")
def download(job_id, filename):
    # sanitize filename
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
