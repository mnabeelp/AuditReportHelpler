"""OCR + structured extraction using the local Ollama vision model."""
import base64
import json
import os
import re
from pathlib import Path

import requests

from .config import OCR_MODEL, OLLAMA_BASE_URL, OCR_TIMEOUT, RUNPOD_ENDPOINT_URL
from PIL import Image


MAX_IMAGE_SIDE = int(os.getenv("MAX_IMAGE_SIDE", "1280"))


def _resize_image(path: str) -> str:
    """Resize image to MAX_IMAGE_SIDE on longest side for faster OCR. Returns path (may be new)."""
    try:
        img = Image.open(path)
        w, h = img.size
        if max(w, h) <= MAX_IMAGE_SIDE:
            return path
        scale = MAX_IMAGE_SIDE / max(w, h)
        new = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        out = path.rsplit(".", 1)[0] + "_rs.png"
        new.save(out)
        return out
    except Exception:
        return path


def _image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _pdf_pages_to_images(path: str, dpi: int = 200) -> list[str]:
    """Render PDF pages to temporary PNG files; return their paths."""
    import fitz  # pymupdf

    out_dir = Path(path).parent / ".audit_pages"
    out_dir.mkdir(exist_ok=True)
    doc = fitz.open(path)
    images = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi)
        img_path = out_dir / f"{Path(path).stem}_p{i + 1}.png"
        pix.save(str(img_path))
        images.append(_resize_image(str(img_path)))
    doc.close()
    return images


def prepare_images(input_path: str) -> list[str]:
    """Return a list of image file paths to OCR (handles images and PDFs)."""
    p = Path(input_path)
    if not p.exists():
        raise FileNotFoundError(input_path)
    ext = p.suffix.lower()
    if ext == ".pdf":
        return _pdf_pages_to_images(str(p))
    if ext in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}:
        return [_resize_image(str(p))]
    raise ValueError(f"Unsupported file type: {ext}")


EXTRACTION_PROMPT = """You are an audit/bookkeeping assistant. Analyze the document image(s) and extract ALL financial entries (line items, invoices, receipts, transactions) you can find.

Return ONLY a valid JSON array. Each element must be an object with these keys (use null when unknown):
- "date": string in YYYY-MM-DD format (or null)
- "vendor": string (counterparty / payee / supplier)
- "doc_number": string (invoice/receipt/transaction number)
- "description": string (what the entry is for)
- "account": string (expense/income account category, e.g. "Office Supplies", "Travel", "Revenue")
- "amount": number (numeric value, positive)
- "tax": number (tax amount if shown, else 0)
- "currency": string (ISO code, default USD)
- "payment_mode": string (cash/card/bank/cheque/online or null)
- "paid_through": string (bank/cash account name or null)
- "notes": string (any extra info)

Rules:
- Do NOT invent data. Use null/0 when a field is not present.
- Amounts must be numbers, not strings.
- If multiple line items exist, return one object per line item.
- Output ONLY the JSON array, no markdown, no commentary.
"""


def extract_entries(image_paths: list[str], base_url: str = None) -> list[dict]:
    """Run OCR+extraction on the given images and return a list of entry dicts."""
    images_b64 = [_image_to_base64(p) for p in image_paths]

    payload = {
        "model": OCR_MODEL,
        "prompt": EXTRACTION_PROMPT,
        "images": images_b64,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    url_base = base_url or (RUNPOD_ENDPOINT_URL if RUNPOD_ENDPOINT_URL else OLLAMA_BASE_URL)
    url = f"{url_base}/api/generate"
    resp = requests.post(url, json=payload, timeout=OCR_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    raw = (data.get("response") or "").strip()

    # Strip markdown fences if present.
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    # Try to locate a JSON array in the response.
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        raw = match.group(0)

    try:
        entries = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: try to find any JSON object list
        entries = []
    if not isinstance(entries, list):
        entries = [entries] if isinstance(entries, dict) else []
    # Cost tracking: use prompt_eval_count and eval_count from Ollama response
    try:
        from . import cost
        cost.init_session()
        cost.record_scan(
            data.get("prompt_eval_count", 0),
            data.get("eval_count", 0),
        )
    except Exception:
        pass
    return entries


def ocr_text(image_paths: list[str], base_url: str = None) -> str:
    """Plain OCR: return raw text from images (no structuring)."""
    images_b64 = [_image_to_base64(p) for p in image_paths]
    payload = {
        "model": OCR_MODEL,
        "prompt": "Extract ALL text from these document images verbatim, preserving layout as much as possible. Return only the text.",
        "images": images_b64,
        "stream": False,
        "options": {"temperature": 0.0},
    }
    url_base = base_url or (RUNPOD_ENDPOINT_URL if RUNPOD_ENDPOINT_URL else OLLAMA_BASE_URL)
    url = f"{url_base}/api/generate"
    resp = requests.post(url, json=payload, timeout=OCR_TIMEOUT)
    resp.raise_for_status()
    return (resp.json().get("response") or "").strip()
