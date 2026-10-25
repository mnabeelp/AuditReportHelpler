# Audit Report Helper

OCR documents/images -> structured Excel table -> bookkeeping export (Zoho Books).

## Features

- OCR + structured extraction from images and PDFs using a **local** vision model.
- Writes an Excel workbook (`.xlsx`) with a formatted "Audit Entries" sheet and a "Summary" sheet.
- Exports a generic CSV and a **Zoho Books**-compatible CSV (Expenses import template).
- **Mobile-friendly web app**: capture via camera or upload files from a phone.
- CLI for batch processing.

## Local model variant chosen

`qwen2.5vl:7b` (Qwen2.5-VL, 8.3B params, Q4_K_M) — the vision-capable variant in the
local Ollama instance. It is the only model available that can read text from images, so it
is used for OCR and structured field extraction. Configure via env vars:

- `OLLAMA_BASE_URL` (default `http://localhost:11434`)
- `OCR_MODEL` (default `qwen2.5vl:7b`)
- `OCR_TIMEOUT` (default `300` seconds)

## Setup

```bash
cd AuditReportHelpler
uv sync
```

Ensure Ollama is running with the model pulled:

```bash
ollama pull qwen2.5vl:7b
```

## CLI usage

```bash
uv run audit-helper scan path/to/invoice.png -o ./output
uv run audit-helper scan path/to/doc.pdf --dump-json
uv run audit-helper scan path/to/img.jpg --text-only
```

Outputs in `./output`: `<name>_audit.xlsx`, `<name>_audit.csv`, `<name>_zoho.csv`.

## Mobile / web app

Start the server (binds to 0.0.0.0:5000 by default):

```bash
uv run audit-helper-web
```

Open `http://<your-machine-ip>:5000` on your phone. Use **Take Photo** (camera capture) or
**Choose Files** to upload images/PDFs, then **Scan & Export** to get download links.

Env: `HOST`, `PORT`, `UPLOAD_DIR`.

## Notes

- OCR runs on CPU by default and can be slow (minutes per page). A GPU is recommended.
- Extraction quality depends on image clarity; use high-resolution scans.
