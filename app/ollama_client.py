"""
app/ollama_client.py — Ollama connectivity and model management.

Provides:
- Connection check (is Ollama running?)
- List installed models
- Graceful fallback when Ollama is not running
- Pull instructions for recommended models
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import OLLAMA_BASE_URL, SUPPORTED_MODELS
from app.errors import OllamaConnectionError

logger = logging.getLogger(__name__)

# Timeout for connectivity checks
_CHECK_TIMEOUT = 3.0


def is_ollama_running() -> bool:
    """Return True if the Ollama server is reachable at OLLAMA_BASE_URL."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=_CHECK_TIMEOUT)
        return resp.status_code == 200
    except Exception as exc:
        logger.debug("Ollama not reachable: %s", exc)
        return False


def list_installed_models() -> list[str]:
    """Return a list of model names currently installed in Ollama.

    Returns an empty list if Ollama is not running (no exception raised).
    """
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=_CHECK_TIMEOUT)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        models = data.get("models", [])
        return [m["name"] for m in models]
    except Exception as exc:
        logger.warning("Could not list Ollama models: %s", exc)
        return []


def get_available_supported_models() -> list[str]:
    """Return the subset of SUPPORTED_MODELS that are installed."""
    installed = list_installed_models()
    return [m for m in SUPPORTED_MODELS if any(m in i for i in installed)]


def get_pull_instructions(model: str) -> str:
    """Return the ollama pull command for the given model."""
    return f"ollama pull {model}"


def get_all_pull_instructions() -> str:
    """Return pull commands for all supported models."""
    lines = ["# Pull recommended models (start with qwen3:8b for 16GB RAM)"]
    for model in SUPPORTED_MODELS:
        lines.append(f"ollama pull {model}")
    return "\n".join(lines)


def assert_ollama_running() -> None:
    """Raise OllamaConnectionError if Ollama is not reachable."""
    if not is_ollama_running():
        raise OllamaConnectionError(
            f"Cannot connect to Ollama at {OLLAMA_BASE_URL}.\n"
            "Make sure Ollama is installed and running:\n"
            "  1. Download from https://ollama.com\n"
            "  2. Start: ollama serve\n"
            "  3. Pull a model: ollama pull qwen3:8b\n"
        )
