"""
tools/registry.py — Tool registration decorator with five import-time checks.

The ``@register_tool`` decorator is applied to handler functions at module
import time.  It runs five mandatory checks and raises ``RegistrationError``
immediately if any check fails — meaning an incorrectly declared tool is a
*startup* failure, not a runtime one.

The five checks
---------------
1. The function has a non-empty docstring (description).
2. A ``row_limit`` parameter is declared in the function signature.
3. The first parameter's annotation is a subclass of ``ToolInput``.
4. That input model is configured with ``extra="forbid"``.
5. The tool name is unique — no duplicate registrations.

Usage
-----
::

    from tools.registry import register_tool

    @register_tool
    def my_tool(req: MyRequest) -> MyResult:
        \"\"\"Short description of what this tool does.\"\"\"
        ...
"""

from __future__ import annotations

import inspect
import typing
from dataclasses import dataclass
from typing import Callable, Any

from pydantic import ConfigDict

from tools.models import ToolInput

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class RegistrationError(Exception):
    """Raised at import time when a tool violates registration requirements."""


@dataclass(frozen=True)
class ToolEntry:
    """Metadata stored in the registry for each registered tool."""

    name: str
    description: str
    handler: Callable[..., Any]
    input_model: type[ToolInput]
    row_limit: int
    module: str


# ---------------------------------------------------------------------------
# Registry (module-level singleton)
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, ToolEntry] = {}
"""
The global tool registry.  Keys are tool names (function names).
Populated at import time by ``@register_tool``.
"""


# ---------------------------------------------------------------------------
# Helper: extract the declared row_limit default from a function signature
# ---------------------------------------------------------------------------

def _extract_row_limit(fn: Callable[..., Any]) -> int:
    """Return the *default* value of the ``row_limit`` parameter.

    The ``row_limit`` must be a keyword argument on the *input model*, not on
    the handler function itself.  We inspect the input model's fields to find
    it.  The handler just needs to *accept* a single positional argument whose
    type annotation is the input model.

    Raises ``RegistrationError`` if no ``row_limit`` is declared.
    """
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())

    # The first non-self parameter should be the request model
    if not params:
        raise RegistrationError(
            f"{fn.__qualname__}: handler has no parameters; "
            "expected a single input-model argument."
        )

    first_param = params[0]
    annotation = first_param.annotation

    if annotation is inspect.Parameter.empty:
        raise RegistrationError(
            f"{fn.__qualname__}: first parameter has no type annotation."
        )

    # Resolve lazy string annotations (from __future__ import annotations)
    try:
        hints = typing.get_type_hints(fn)
        annotation = hints.get(first_param.name, annotation)
    except Exception:
        pass  # keep the raw annotation; isinstance check below will catch it

    # Check the input model has a row_limit field
    if not hasattr(annotation, "model_fields") or "row_limit" not in annotation.model_fields:
        raise RegistrationError(
            f"{fn.__qualname__}: input model {annotation.__name__!r} does not "
            "declare a 'row_limit' field.  Every tool must declare an explicit "
            "row limit so that output can be bounded and truncation flags set."
        )

    # Return the field's default value (could be a FieldInfo default)
    model_field = annotation.model_fields["row_limit"]
    default = model_field.default
    if default is None or isinstance(default, type(...)):
        raise RegistrationError(
            f"{fn.__qualname__}: 'row_limit' in {annotation.__name__!r} has no "
            "default value.  A concrete numeric default is required."
        )
    return int(default)


# ---------------------------------------------------------------------------
# Helper: extract input model class from handler signature
# ---------------------------------------------------------------------------

def _extract_input_model(fn: Callable[..., Any]) -> type[ToolInput]:
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    if not params:
        raise RegistrationError(
            f"{fn.__qualname__}: handler has no parameters."
        )
    first_param = params[0]
    if first_param.annotation is inspect.Parameter.empty:
        raise RegistrationError(
            f"{fn.__qualname__}: first parameter has no type annotation."
        )
    # Resolve lazy string annotations produced by `from __future__ import annotations`
    try:
        hints = typing.get_type_hints(fn)
        annotation = hints.get(first_param.name, first_param.annotation)
    except Exception:
        # Fall back to the raw annotation (may be a string or the class itself)
        annotation = first_param.annotation
    return annotation


# ---------------------------------------------------------------------------
# The decorator
# ---------------------------------------------------------------------------

def register_tool(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Register *fn* as a tool, running five checks at import time.

    Checks (in order)
    -----------------
    1. Non-empty docstring.
    2. ``row_limit`` declared on the input model.
    3. First parameter annotated with a ``ToolInput`` subclass.
    4. That model's ``extra`` config is ``"forbid"``.
    5. Tool name is unique in ``TOOL_REGISTRY``.

    Raises
    ------
    RegistrationError
        If any check fails.  Because this runs at module import time the
        process will not start with a misconfigured tool.
    """
    name = fn.__name__

    # ------------------------------------------------------------------
    # Check 1: non-empty docstring
    # ------------------------------------------------------------------
    doc = inspect.getdoc(fn)
    if not doc:
        raise RegistrationError(
            f"Tool '{name}' ({fn.__qualname__}) has no docstring.  "
            "Every tool must have a description so that the manifest is "
            "informative and the tool can be understood without reading source."
        )

    # ------------------------------------------------------------------
    # Check 3: first parameter annotated with a ToolInput subclass
    # (done before check 2 so the error about row_limit is meaningful)
    # ------------------------------------------------------------------
    input_model = _extract_input_model(fn)
    if not (isinstance(input_model, type) and issubclass(input_model, ToolInput)):
        raise RegistrationError(
            f"Tool '{name}': first parameter must be annotated with a "
            f"ToolInput subclass, got {input_model!r}.  Wrap your request "
            "fields in a class that inherits from tools.models.ToolInput."
        )

    # ------------------------------------------------------------------
    # Check 2: row_limit declared on the input model
    # ------------------------------------------------------------------
    row_limit = _extract_row_limit(fn)

    # ------------------------------------------------------------------
    # Check 4: input model has extra="forbid"
    # ------------------------------------------------------------------
    model_config: ConfigDict = getattr(input_model, "model_config", {})
    extra_setting = model_config.get("extra", None)
    if extra_setting != "forbid":
        raise RegistrationError(
            f"Tool '{name}': input model {input_model.__name__!r} must be "
            f"configured with extra='forbid' (got extra={extra_setting!r}).  "
            "This ensures malformed arguments never reach the handler."
        )

    # ------------------------------------------------------------------
    # Check 5: unique name
    # ------------------------------------------------------------------
    if name in TOOL_REGISTRY:
        raise RegistrationError(
            f"Tool '{name}' is already registered.  "
            "Duplicate tool names are not allowed; rename one of them."
        )

    # ------------------------------------------------------------------
    # All checks passed — record in the registry
    # ------------------------------------------------------------------
    TOOL_REGISTRY[name] = ToolEntry(
        name=name,
        description=doc,
        handler=fn,
        input_model=input_model,
        row_limit=row_limit,
        module=fn.__module__,
    )

    return fn
