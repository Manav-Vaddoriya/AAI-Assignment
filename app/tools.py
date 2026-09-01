"""
app/tools.py — Tool definitions in Ollama-compatible format.

Converts the TOOL_REGISTRY entries to the JSON format that Ollama's
tool-calling API expects:

    {
        "type": "function",
        "function": {
            "name": "get_product",
            "description": "...",
            "parameters": { <JSON Schema> }
        }
    }

The schema is generated directly from the Pydantic model — no manual
maintenance needed.
"""

from __future__ import annotations

from typing import Any

from app.registry import TOOL_REGISTRY


def get_ollama_tool_definitions() -> list[dict[str, Any]]:
    """Return tool definitions in Ollama API format.

    Only production tools (not test stubs starting with '_test') are included.
    """
    definitions = []
    for name, entry in TOOL_REGISTRY.items():
        if name.startswith("_test"):
            continue
        schema = entry.input_model.model_json_schema()
        # Remove Pydantic-internal keys not needed by Ollama
        schema.pop("title", None)
        schema.pop("description", None)
        definitions.append({
            "type": "function",
            "function": {
                "name": name,
                "description": entry.description,
                "parameters": schema,
            },
        })
    return definitions
