"""Cost tracking for RunPod OCR scans (budget cap $2)."""
import os
import time
from datetime import datetime
from pathlib import Path

from .config import MAX_SPEND_USD, RUNPOD_HOURLY_RATE, TOKENS_PER_SECOND

DATA = {}


def init_session():
    DATA["start"] = time.time()
    DATA["tokens_in"] = 0
    DATA["tokens_out"] = 0
    DATA["scans"] = 0


def record_scan(prompt_tokens: int, output_tokens: int):
    DATA["scans"] += 1
    DATA["tokens_in"] += prompt_tokens
    DATA["tokens_out"] += output_tokens


def estimate_cost() -> float:
    """Rough USD estimate from GPU time (not token-rate)."""
    elapsed = time.time() - DATA.get("start", time.time())
    hours = elapsed / 3600.0
    return hours * RUNPOD_HOURLY_RATE


def check_budget() -> bool:
    return estimate_cost() <= MAX_SPEND_USD


def get_status() -> dict:
    return {
        "scans": DATA.get("scans", 0),
        "tokens_in": DATA.get("tokens_in", 0),
        "tokens_out": DATA.get("tokens_out", 0),
        "elapsed_sec": round(time.time() - DATA.get("start", time.time()), 1),
        "estimated_usd": round(estimate_cost(), 4),
        "budget": MAX_SPEND_USD,
        "under_budget": check_budget(),
    }
