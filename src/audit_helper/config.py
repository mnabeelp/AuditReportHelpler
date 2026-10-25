"""Configuration for the Audit Report Helper."""
import os

# Local Ollama endpoint and the chosen vision-capable variant for OCR.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# qwen2.5vl:7b is the vision-capable local variant chosen for OCR/extraction.
OCR_MODEL = os.getenv("OCR_MODEL", "qwen2.5vl:7b")

# Request timeout for a single OCR/extraction call (seconds).
OCR_TIMEOUT = int(os.getenv("OCR_TIMEOUT", "300"))

# Default currency for extracted entries.
DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "USD")

# RunPod Serverless endpoint (optional override for remote Ollama endpoint)
RUNPOD_ENDPOINT_URL = os.getenv("RUNPOD_ENDPOINT_URL", None)
# Max spend per session/document in USD to enforce budget ceiling
MAX_SPEND_USD = float(os.getenv("MAX_SPEND_USD", "2.00"))
# Approx RunPod GPU hourly rate used for rough cost estimation (shared A10G)
RUNPOD_HOURLY_RATE = float(os.getenv("RUNPOD_HOURLY_RATE", "0.22"))
# Tokens per second rough GPU throughput estimate for qwen2.5vl:7b
TOKENS_PER_SECOND = int(os.getenv("TOKENS_PER_SECOND", "80"))
