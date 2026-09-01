"""
app/registry.py — Central tool registry for the P13 agent system.

The registry is the single source of truth for all registered tools.
It is populated at import time by the ``@read_tool`` decorator in
``app/decorators.py``.

No tool metadata should be maintained manually.  The manifest is generated
directly from this registry.

Usage
-----
::

    from app.registry import TOOL_REGISTRY

    entry = TOOL_REGISTRY["get_product"]
    result = entry.handler(validated_input)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolEntry:
    """Metadata stored in the registry for each registered tool.

    Attributes
    ----------
    name:
        Unique tool name used as the registry key.
    description:
        Human-readable description (sourced from ``@read_tool`` args).
    handler:
        The callable that executes the tool logic.
    input_model:
        The Pydantic BaseModel class used to validate tool arguments.
    row_limit:
        Maximum rows this tool may return in a single call.
    read_only:
        Always True for P13 tools — enforced by the decorator.
    module:
        Fully-qualified module name where the handler is defined.
    """

    name: str
    description: str
    handler: Callable[..., Any]
    input_model: type[BaseModel]
    row_limit: int
    read_only: bool
    module: str


#: The global tool registry — keys are tool names.
#: Populated at import time by @read_tool.  Never write to this directly.
TOOL_REGISTRY: dict[str, ToolEntry] = {}
