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
