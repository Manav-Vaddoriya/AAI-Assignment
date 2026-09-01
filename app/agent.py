"""
app/agent.py — Agentic loop using Ollama.

Architecture
------------
::

    User message
         ↓
    LLM (Ollama) with tool definitions
         ↓
    Tool call response (name + JSON args)
         ↓
    Registry lookup
         ↓
    Pydantic validation (raises ToolValidationError if malformed)
         ↓
    Handler execution
         ↓
    Tool result → LLM
         ↓
    Final natural-language answer

The LLM NEVER touches the database directly.
Malformed tool arguments are blocked by Pydantic before the handler runs.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Generator

from pydantic import ValidationError

import app.handlers  # noqa: F401 — populate registry
from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from app.errors import OllamaConnectionError, ToolExecutionError, ToolValidationError
from app.ollama_client import is_ollama_running
from app.registry import TOOL_REGISTRY
from app.tools import get_ollama_tool_definitions

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a read-only data assistant for the P13 agent system.

You may ONLY retrieve information through the registered tools: get_product, get_user, get_user_orders.

Rules you must follow:
- Never invent database results.
- Never generate or execute SQL.
- Never bypass tool validation.
- If a tool rejects an argument, explain the validation failure and ask the user for a corrected value.
- Respect the returned row limits.
- If a result is truncated, explicitly tell the user that only the allowed number of rows were returned.
- Do not claim that additional data was inspected unless the tool actually returned it.
- Do not expose internal implementation details to the user.

Available identifiers:
- Products: P followed by digits, e.g. P1001
- Users: U followed by digits, e.g. U1001
"""


# ---------------------------------------------------------------------------
# Data structures for the agent trace
# ---------------------------------------------------------------------------

@dataclass
class TraceEvent:
    """A single step in the agent's execution trace."""
    event: str
    detail: str = ""
    success: bool = True


@dataclass
class AgentResponse:
    """The complete response from one agent turn."""
    answer: str
    trace: list[TraceEvent] = field(default_factory=list)
    tool_calls_made: int = 0
    error: str | None = None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class P13Agent:
    """Agentic loop over Ollama with P13 registered tools."""

    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model = model or OLLAMA_MODEL
        self.base_url = base_url or OLLAMA_BASE_URL
        self._tool_defs = get_ollama_tool_definitions()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def chat(self, user_message: str) -> AgentResponse:
        """Run the agentic loop for one user message.

        Returns an AgentResponse regardless of whether Ollama is available.
        If Ollama is down, returns a helpful error message.
        """
        trace: list[TraceEvent] = []
        t0 = time.perf_counter()

        # Connection check
        if not is_ollama_running():
            return AgentResponse(
                answer=(
                    "Ollama is not running.  "
                    f"Start it and pull a model:\n  ollama pull {self.model}"
                ),
                error="ollama_not_running",
                trace=[TraceEvent("connection_check", "Ollama unreachable", success=False)],
            )

        trace.append(TraceEvent("connection_check", f"Ollama reachable at {self.base_url}"))
        trace.append(TraceEvent("model_selected", self.model))

        try:
            import ollama  # lazy import — only needed at runtime
        except ImportError:
            return AgentResponse(
                answer="The 'ollama' Python package is not installed. Run: pip install ollama",
                error="ollama_package_missing",
            )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        tool_calls_made = 0
        max_iterations = 5  # prevent infinite loops

        for _iteration in range(max_iterations):
            try:
                response = ollama.chat(
                    model=self.model,
                    messages=messages,
                    tools=self._tool_defs,
                )
            except Exception as exc:
                logger.error("Ollama chat error: %s", exc)
                return AgentResponse(
                    answer=f"Model error: {exc}",
                    error=str(exc),
                    trace=trace,
                )

            msg = response.message

            # If the model wants to call tools
            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.function.name
                    raw_args: dict[str, Any] = dict(tool_call.function.arguments or {})

                    trace.append(TraceEvent(
                        "tool_selected",
                        f"Tool: {tool_name} | Args: {json.dumps(raw_args)}",
                    ))
                    logger.info("tool_selected tool=%s args=%s", tool_name, raw_args)

                    # Registry lookup
                    if tool_name not in TOOL_REGISTRY:
                        tool_result = f"Error: tool '{tool_name}' is not registered."
                        trace.append(TraceEvent("tool_error", tool_result, success=False))
                        messages.append({"role": "tool", "content": tool_result})
                        continue

                    entry = TOOL_REGISTRY[tool_name]

                    # Pydantic validation (malformed args blocked here)
                    try:
                        validated = entry.input_model(**raw_args)
                        trace.append(TraceEvent("validation", "Arguments validated", success=True))
                        logger.info("validation=passed tool=%s", tool_name)
                    except ValidationError as exc:
                        errors = exc.errors(include_url=False)
                        error_summary = "; ".join(
                            f"{e['loc']}: {e['msg']}" for e in errors
                        )
                        tool_result = (
                            f"Validation failed for '{tool_name}': {error_summary}.  "
                            "Please provide corrected arguments."
                        )
                        trace.append(TraceEvent("validation", error_summary, success=False))
                        logger.warning(
                            "validation=failed tool=%s errors=%s", tool_name, error_summary
                        )
                        messages.append({
                            "role": "tool",
                            "content": tool_result,
                            "name": tool_name,
                        })
                        continue

                    # Execute handler
                    try:
                        result = entry.handler(validated)
                        tool_calls_made += 1
                        result_dict = result.model_dump()
                        result_json = json.dumps(result_dict, default=str)

                        rows_returned = result_dict.get("count", 1)
                        truncated = result_dict.get("truncated", False)
                        trace.append(TraceEvent(
                            "handler_executed",
                            f"rows={rows_returned} truncated={truncated}",
                        ))
                        logger.info(
                            "handler_executed tool=%s rows=%s truncated=%s",
                            tool_name, rows_returned, truncated,
                        )

                        messages.append({
                            "role": "tool",
                            "content": result_json,
                            "name": tool_name,
                        })
                    except Exception as exc:
                        logger.error("Handler error: %s", exc)
                        tool_result = f"Handler error for '{tool_name}': {exc}"
                        trace.append(TraceEvent("handler_error", str(exc), success=False))
                        messages.append({
                            "role": "tool",
                            "content": tool_result,
                            "name": tool_name,
                        })

                # Add assistant message with tool_calls before continuing
                messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                    {"function": {"name": tc.function.name, "arguments": dict(tc.function.arguments or {})}}
                    for tc in msg.tool_calls
                ]})

            else:
                # Model produced a final answer (no more tool calls)
                duration_ms = round((time.perf_counter() - t0) * 1000, 1)
                trace.append(TraceEvent("final_answer", f"duration_ms={duration_ms}"))
                
                final_answer = msg.content
                if not final_answer and tool_calls_made > 0:
                    final_answer = "*(The AI fetched the data successfully but didn't write a summary. Check the trace to see the data it found!)*"
                elif not final_answer:
                    final_answer = "(no response)"
                    
                return AgentResponse(
                    answer=final_answer,
                    trace=trace,
                    tool_calls_made=tool_calls_made,
                )

        # Fell through max_iterations — return last message content
        return AgentResponse(
            answer="Maximum tool call iterations reached.  Please try a simpler question.",
            trace=trace,
            tool_calls_made=tool_calls_made,
            error="max_iterations",
        )
