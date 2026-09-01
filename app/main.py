"""
app/main.py — Uvicorn entry point for the P13 FastAPI application.

Run with:
    uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
"""

from __future__ import annotations

import logging

from app.api import app  # noqa: F401 — re-export for uvicorn
from app.config import LOG_LEVEL

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)
logger.info("P13 Agent Tool System starting up.")
