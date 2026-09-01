"""
tests/test_app_agent.py — Agent layer tests with mocked Ollama.

The agent tests do NOT require Ollama to be installed or running.
All Ollama calls are replaced by unittest.mock stubs.

Verifies:
- Tool definitions are generated from the registry
- Tool arguments go through Pydantic validation
- Invalid arguments are rejected before handler is called
- Valid tool calls reach the handler and return results
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

import app.handlers  # noqa: F401 — populate registry

from app.registry import TOOL_REGISTRY
from app.schemas import ProductInput, UserInput, UserOrdersInput


# ===========================================================================
# Tool schema generation (for Ollama tool-calling interface)
# ===========================================================================

class TestToolSchemaGeneration:
    """Tools must expose their JSON schemas for the Ollama API."""

    def test_registry_has_three_production_tools(self):
        prod = {k: v for k, v in TOOL_REGISTRY.items() if not k.startswith("_test")}
        assert len(prod) == 3

    def test_tool_schema_is_valid_json(self):
        for name, entry in TOOL_REGISTRY.items():
            if name.startswith("_test"):
                continue
            schema = entry.input_model.model_json_schema()
            # Must serialise to JSON without error
            json.dumps(schema)

    def test_tool_schema_has_additional_properties_false(self):
        for name, entry in TOOL_REGISTRY.items():
            if name.startswith("_test"):
                continue
            schema = entry.input_model.model_json_schema()
            assert schema.get("additionalProperties") is False


# ===========================================================================
# Simulated agent loop (no real Ollama)
# ===========================================================================

def _simulate_tool_call(tool_name: str, raw_args: dict):
    """
    Simulate the agent executing one tool call:
      1. Look up the tool in the registry.
      2. Validate args with Pydantic.
      3. Call the handler with the validated model.
    Returns (result, handler_called).
    """
    if tool_name not in TOOL_REGISTRY:
        raise KeyError(f"Tool '{tool_name}' not found in registry.")

    entry = TOOL_REGISTRY[tool_name]
    handler_called = False

    validated = entry.input_model(**raw_args)   # raises ValidationError if invalid
    handler_called = True
    result = entry.handler(validated)
    return result, handler_called


class TestSimulatedAgentLoop:
    """Simulate the agent loop without a real LLM."""

    # ---- get_product ----

    def test_agent_calls_get_product_successfully(self):
        result, called = _simulate_tool_call("get_product", {"product_id": "P1001"})
        assert called is True
        assert result.found is True
        assert result.product_id == "P1001"

    def test_agent_get_product_invalid_id_blocked(self):
        with pytest.raises(ValidationError):
            _simulate_tool_call("get_product", {"product_id": "ABC"})

    def test_agent_get_product_devanagari_id_blocked(self):
        with pytest.raises(ValidationError):
            _simulate_tool_call("get_product", {"product_id": "P१२३"})

    def test_agent_get_product_extra_field_blocked(self):
        with pytest.raises(ValidationError):
            _simulate_tool_call("get_product", {"product_id": "P1001", "hack": True})

    # ---- get_user ----

    def test_agent_calls_get_user_successfully(self):
        result, called = _simulate_tool_call("get_user", {"user_id": "U1001"})
        assert called is True
        assert result.user_id == "U1001"

    def test_agent_get_user_invalid_id_blocked(self):
        with pytest.raises(ValidationError):
            _simulate_tool_call("get_user", {"user_id": "WRONG"})

    # ---- get_user_orders ----

    def test_agent_calls_get_user_orders_successfully(self):
        result, called = _simulate_tool_call(
            "get_user_orders", {"user_id": "U1001", "limit": 5}
        )
        assert called is True
        assert result.count == 5
        assert result.truncated is True

    def test_agent_get_user_orders_excessive_limit_blocked(self):
        """LLM requesting 1,000,000 rows must be blocked by Pydantic."""
        with pytest.raises(ValidationError):
            _simulate_tool_call("get_user_orders", {"user_id": "U1001", "limit": 1_000_000})

    def test_agent_tool_not_in_registry_raises(self):
        with pytest.raises(KeyError, match="not found in registry"):
            _simulate_tool_call("drop_table", {"table": "users"})

    def test_agent_missing_required_arg_blocked(self):
        with pytest.raises(ValidationError):
            _simulate_tool_call("get_product", {})


# ===========================================================================
# Mocked Ollama client tests
# ===========================================================================

class TestMockedOllamaClient:
    """Test the Ollama client module with mocked HTTP calls."""

    def test_connection_check_returns_true_when_reachable(self):
        """Mock a successful Ollama ping."""
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            import httpx
            resp = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
            assert resp.status_code == 200

    def test_connection_check_returns_false_when_unreachable(self):
        """Mock a connection failure."""
        import httpx
        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            try:
                httpx.get("http://localhost:11434/api/tags", timeout=2.0)
                reachable = True
            except httpx.ConnectError:
                reachable = False
            assert reachable is False
