"""
app/decorators.py — ``@read_tool`` registration decorator with five import-time checks.

Usage
-----
::

    from app.decorators import read_tool

    @read_tool(
        name="get_product",
        description="Retrieve product information by product ID.",
        row_limit=1,
    )
    def get_product(req: ProductInput) -> ProductResult:
        ...

The five checks (run at IMPORT TIME, not at call time)
------------------------------------------------------
1. Description must be a non-empty string.
2. row_limit must be a positive integer.
3. The handler's first parameter must be annotated with a BaseModel subclass.
4. That input model must have ``extra="forbid"`` in its model_config.
5. The tool name must be unique — no duplicate registrations allowed.

If any check fails, ``ToolRegistrationError`` is raised immediately, preventing
the application from starting with a misconfigured tool.
"""

from __future__ import annotations

import inspect
import typing
from typing import Any, Callable

from pydantic import BaseModel

from app.errors import ToolRegistrationError

# Registry is imported lazily inside the decorator to avoid circular imports.
# We reference it by name so the import happens after the module is loaded.


def read_tool(
    name: str,
    description: str,
    row_limit: int,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory that registers a read-only tool.

    Parameters
    ----------
    name:
        Unique tool name (used in the registry and manifest).
    description:
        Human-readable description.  Must be non-empty.
    row_limit:
        Maximum rows this tool may return.  Must be a positive integer.

    Returns
    -------
    Callable
        A decorator that registers the handler and returns it unchanged.

    Raises
    ------
    ToolRegistrationError
        Immediately at import time if any of the five checks fails.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        # ------------------------------------------------------------------
        # Check 1: description must be a non-empty string
        # ------------------------------------------------------------------
        if not isinstance(description, str) or not description.strip():
            raise ToolRegistrationError(
                f"Tool '{name}' cannot be registered: missing description.\n"
                "Every tool must have a non-empty description so the manifest "
                "is informative and the tool can be discovered without reading source."
            )

        # ------------------------------------------------------------------
        # Check 2: row_limit must be a positive integer
        # ------------------------------------------------------------------
        if not isinstance(row_limit, int) or isinstance(row_limit, bool) or row_limit < 1:
            raise ToolRegistrationError(
                f"Tool '{name}' cannot be registered: missing or invalid row_limit.\n"
                f"Got {row_limit!r}.  row_limit must be a positive integer (>= 1)."
            )

        # ------------------------------------------------------------------
        # Check 3: first parameter must be annotated with a BaseModel subclass
        # ------------------------------------------------------------------
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        if not params:
            raise ToolRegistrationError(
                f"Tool '{name}' cannot be registered: handler has no parameters.\n"
                "Expected a single positional argument whose type is a Pydantic BaseModel."
            )

        first_param = params[0]
        if first_param.annotation is inspect.Parameter.empty:
            raise ToolRegistrationError(
                f"Tool '{name}' cannot be registered: first parameter "
                f"'{first_param.name}' has no type annotation.\n"
                "Annotate it with the corresponding Pydantic input model."
            )

        # Resolve forward references (from __future__ import annotations)
        # Fall back to the raw annotation if get_type_hints fails — this
        # happens for classes defined inside test functions/methods.
        raw_annotation = first_param.annotation
        try:
            hints = typing.get_type_hints(fn)
            input_model = hints.get(first_param.name, raw_annotation)
        except Exception:
            input_model = raw_annotation

        # If still unresolved, use raw annotation
        if isinstance(input_model, str):
            input_model = raw_annotation

        if not (isinstance(input_model, type) and issubclass(input_model, BaseModel)):
            raise ToolRegistrationError(
                f"Tool '{name}' cannot be registered: first parameter "
                f"annotation is {input_model!r}, which is not a Pydantic BaseModel "
                "subclass.  Wrap inputs in a class that inherits from BaseModel."
            )

        # ------------------------------------------------------------------
        # Check 4: input model must have extra="forbid"
        # ------------------------------------------------------------------
        model_cfg = getattr(input_model, "model_config", {})
        extra_setting = model_cfg.get("extra", None)
        if extra_setting != "forbid":
            raise ToolRegistrationError(
                f"Tool '{name}' cannot be registered: input model "
                f"{input_model.__name__!r} must be configured with "
                f"extra='forbid' (currently extra={extra_setting!r}).\n"
                "This ensures malformed arguments are ALWAYS rejected before "
                "the handler is called — a core P13 security invariant."
            )

        # ------------------------------------------------------------------
        # Check 5: tool name must be unique in the registry
        # ------------------------------------------------------------------
        # Deferred import to avoid circular dependency
        from app.registry import TOOL_REGISTRY, ToolEntry  # noqa: PLC0415

        if name in TOOL_REGISTRY:
            raise ToolRegistrationError(
                f"Tool '{name}' cannot be registered: name already exists in the registry.\n"
                "Duplicate tool names are not allowed.  Rename one of them."
            )

        # ------------------------------------------------------------------
        # All five checks passed — record in registry
        # ------------------------------------------------------------------
        TOOL_REGISTRY[name] = ToolEntry(
            name=name,
            description=description.strip(),
            handler=fn,
            input_model=input_model,
            row_limit=row_limit,
            read_only=True,
            module=fn.__module__,
        )

        return fn

    return decorator
