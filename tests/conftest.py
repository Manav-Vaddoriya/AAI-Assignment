"""
tests/conftest.py — Shared pytest fixtures.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session", autouse=True)
def _ensure_app_handlers_imported():
    """Import app.handlers once per test session to populate TOOL_REGISTRY."""
    import app.handlers  # noqa: F401
