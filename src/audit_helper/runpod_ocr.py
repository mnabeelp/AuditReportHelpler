"""RunPod Serverless integration for OCR with qwen2.5vl:7b."""
import os
import time
import base64
import json
import re
from pathlib import Path
from typing import Optional

import requests

from .config import (
    OCR_MODEL, OLLAMA_BASE_URL, OCR_TIMEOUT,
    RUNPOD_ENDPOINT_URL, MAX_SPEND_USD, RUNPOD_HOURLY_RATE, TOKENS_PER_SECOND,
)
from . import cost


RUNPOD_API_URL = "https://api.runpod.io/v2"
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")


def _headers():
    return {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json",
    }


def list_gpu_types() -> list[dict]:
    """List available GPU types for serverless endpoints."""
    resp = requests.get(
        f"{RUNPOD_API_URL}/gpu-types",
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def create_serverless_endpoint(
    name: str = "audit-ocr-qwen",
    gpu_type_id: str = "NVIDIA RTX A4090",
    min_workers: int = 0,
    max_workers: int = 1,
    flash_workers: int = 1,
    execution_timeout: int = 300,
) -> dict:
    """Create a RunPod serverless endpoint for qwen2.5vl:7b."""
    payload = {
        "name": name,
        "gpu_type_id": gpu_type_id,
        "min_workers": min_workers,
        "max_workers": max_workers,
        "flash_workers": flash_workers,
        "execution_timeout": execution_timeout,
        "workers_max": max_workers,
        "template": {
            "image_name": "runpod/pytorch:2.1.0-py3.10-cuda12.1-pytorch2.1",
            "docker_cmd": "ollama serve & sleep 5 && ollama pull qwen2.5vl:7b && ollama serve",
            "container_disk_in_gb": 25,
            "container_network": "no",
            "env": [
                {"name": "OLLAMA_HOST", "value": "0.0.0.0:11434"},
            ],
        },
    }
    resp = requests.post(
        f"{RUNPOD_API_URL}/endpoints",
        headers=_headers(),
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def get_endpoint(endpoint_id: str) -> dict:
    resp = requests.get(
        f"{RUNPOD_API_URL}/endpoints/{endpoint_id}",
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def delete_endpoint(endpoint_id: str) -> dict:
    resp = requests.delete(
        f"{RUNPOD_API_URL}/endpoints/{endpoint_id}",
        headers=_headers(),
        timeout=30,
    )
    return resp.json()


def ollama_compatible_url(endpoint_id: str) -> str:
    """RunPod serverless endpoints expose an Ollama-compatible API."""
    return f"https://api.runpod.io/v2/{endpoint_id}/openai/v1"


def run_ocr(
    image_paths: list[str],
    prompt: str,
    model: str = OCR_MODEL,
    endpoint_url: Optional[str] = None,
    timeout: int = OCR_TIMEOUT,
) -> tuple[str, dict]:
    """Run OCR via RunPod serverless endpoint (Ollama-compatible API).
    Returns (response_text, cost_info).
    """
    images_b64 = []
    for p in image_paths:
        with open(p, "rb") as f:
            images_b64.append(base64.b64encode(f.read()).decode("utf-8"))

    url = endpoint_url or RUNPOD_ENDPOINT_URL or OLLAMA_BASE_URL
    if not url.endswith("/api/generate"):
        url = url.rstrip("/") + "/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "images": images_b64,
        "stream": False,
        "options": {"temperature": 0.1},
    }

    start = time.time()
    resp = requests.post(url, json=payload, timeout=timeout)
    elapsed = time.time() - start
    resp.raise_for_status()
    data = resp.json()
    raw = (data.get("response") or "").strip()

    # Cost tracking
    prompt_tokens = data.get("prompt_eval_count", 0)
    output_tokens = data.get("eval_count", 0)
    cost.record_scan(prompt_tokens, output_tokens)

    cost_info = {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "elapsed_sec": round(elapsed, 1),
        "estimated_usd": round(cost.estimate_cost(), 4),
        "under_budget": cost.check_budget(),
        "max_spend_usd": MAX_SPEND_USD,
    }
    return raw, cost_info


def extract_entries(
    image_paths: list[str],
    base_url: Optional[str] = None,
) -> tuple[list[dict], dict]:
    """Run OCR+extraction via RunPod and return (entries, cost_info)."""
    raw, cost_info = run_ocr(
        image_paths,
        EXTRACTION_PROMPT,
        base_url=base_url,
    )

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
        entries = []
    if not isinstance(entries, list):
        entries = [entries] if isinstance(entries, dict) else []
    return entries, cost_info


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