"""
app/api.py — FastAPI REST API for the P13 tool system.

Endpoints
---------
GET  /health               — Server health + Ollama status
GET  /tools                — List all registered tools (from registry)
POST /tools/{name}/invoke  — Invoke a tool with JSON arguments (validated)
POST /agent/chat           — Natural-language chat through the Ollama agent
GET  /manifest             — Return the committed manifest
GET  /manifest/status      — Check if committed manifest matches live registry
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

import app.handlers  # noqa: F401 — populate TOOL_REGISTRY

from app.config import MANIFEST_PATH
from app.errors import ManifestMismatchError
from app.manifest import check_manifest, generate_manifest
from app.ollama_client import get_available_supported_models, is_ollama_running, list_installed_models
from app.registry import TOOL_REGISTRY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="P13 Agentic Tool System",
    description=(
        "Typed read-only tool API with Pydantic validation, "
        "Ollama agent integration, and manifest drift detection."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class InvokeRequest(BaseModel):
    """Request body for POST /tools/{name}/invoke."""
    arguments: dict[str, Any]


class ChatRequest(BaseModel):
    """Request body for POST /agent/chat."""
    message: str
    model: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, Any]:
    """Server health check including Ollama connectivity status."""
    ollama_up = is_ollama_running()
    installed_models = list_installed_models() if ollama_up else []
    supported = get_available_supported_models()

    prod_tools = {k: v for k, v in TOOL_REGISTRY.items() if not k.startswith("_test")}
    return {
        "status": "ok",
        "tool_count": len(prod_tools),
        "ollama": {
            "running": ollama_up,
            "installed_models": installed_models,
            "supported_available": supported,
        },
    }


@app.get("/tools")
def list_tools() -> dict[str, Any]:
    """List all registered tools with their metadata."""
    prod_tools = {k: v for k, v in TOOL_REGISTRY.items() if not k.startswith("_test")}
    return {
        "count": len(prod_tools),
        "tools": [
            {
                "name": entry.name,
                "description": entry.description,
                "row_limit": entry.row_limit,
                "read_only": entry.read_only,
                "input_schema": entry.input_model.model_json_schema(),
            }
            for entry in prod_tools.values()
        ],
    }


@app.post("/tools/{name}/invoke")
def invoke_tool(name: str, body: InvokeRequest) -> dict[str, Any]:
    """Invoke a registered tool with the given arguments.

    Arguments are validated by Pydantic before the handler is called.
    Returns a 422 error with details if validation fails.
    """
    if name not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found.")

    if name.startswith("_test"):
        raise HTTPException(status_code=404, detail="Tool not found.")

    entry = TOOL_REGISTRY[name]

    try:
        validated = entry.input_model(**body.arguments)
    except ValidationError as exc:
        errors = exc.errors(include_url=False)
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Validation failed for tool '{name}'",
                "errors": errors,
                "handler_called": False,  # Security invariant — handler NOT called
            },
        ) from exc

    try:
        result = entry.handler(validated)
        return {
            "tool": name,
            "handler_called": True,
            "result": result.model_dump(),
        }
    except Exception as exc:
        logger.error("Handler error for %s: %s", name, exc)
        raise HTTPException(status_code=500, detail=f"Tool execution error: {exc}") from exc


@app.post("/agent/chat")
def agent_chat(body: ChatRequest) -> dict[str, Any]:
    """Send a natural-language message to the Ollama agent."""
    from app.agent import P13Agent  # noqa: PLC0415

    agent = P13Agent(model=body.model)
    response = agent.chat(body.message)

    return {
        "answer": response.answer,
        "tool_calls_made": response.tool_calls_made,
        "error": response.error,
        "trace": [
            {"event": e.event, "detail": e.detail, "success": e.success}
            for e in response.trace
        ],
    }


@app.get("/manifest")
def get_manifest() -> dict[str, Any]:
    """Return the live-generated manifest from the registry."""
    return generate_manifest()


@app.get("/manifest/status")
def manifest_status() -> dict[str, Any]:
    """Check whether the committed manifest matches the live registry."""
    try:
        check_manifest(MANIFEST_PATH)
        return {"status": "ok", "message": "Manifest matches registry"}
    except ManifestMismatchError as exc:
        return {"status": "drift", "message": str(exc)}
    except FileNotFoundError as exc:
        return {"status": "missing", "message": str(exc)}
