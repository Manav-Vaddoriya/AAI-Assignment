"""
app/config.py — Centralised configuration loaded from .env / environment variables.

All other modules import from here instead of reading env vars directly,
so there is a single source of truth for every configuration knob.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present (ignored in production where env vars are set externally)
load_dotenv(Path(__file__).parent.parent / ".env", override=False)


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL: str = _env("OLLAMA_BASE_URL", "http://localhost:11434")
"""Base URL of the locally running Ollama server."""

OLLAMA_MODEL: str = _env("OLLAMA_MODEL", "qwen3:8b")
"""Default model name to use when none is selected in the UI."""

# Models supported by the application.
# The app will check which ones are actually installed before use.
SUPPORTED_MODELS: list[str] = [
    "qwen3:8b",
    "llama3.1:8b",
    "mistral-small3.2",
    "gpt-oss:20b",
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASE_PATH: Path = Path(_env("DATABASE_PATH", "./data/demo.db"))
"""Path to the SQLite demo database file."""

# ---------------------------------------------------------------------------
# Row limits
# ---------------------------------------------------------------------------

MAX_ROWS: int = int(_env("MAX_ROWS", "100"))
"""Global hard maximum number of rows any tool may return."""

# Per-tool defaults (also enforced by Pydantic field constraints)
PRODUCT_ROW_LIMIT: int = 1      # get_product — single row by ID
USER_ROW_LIMIT: int = 1         # get_user — single row by ID
ORDERS_ROW_LIMIT_DEFAULT: int = 20
ORDERS_ROW_LIMIT_MAX: int = min(MAX_ROWS, 100)

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

API_HOST: str = _env("API_HOST", "127.0.0.1")
API_PORT: int = int(_env("API_PORT", "8000"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL: str = _env("LOG_LEVEL", "INFO")

# Path to the committed manifest (for drift detection)
MANIFEST_PATH: Path = Path(__file__).parent.parent / "manifests" / "tools.json"
