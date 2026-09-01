"""app/errors.py — Custom exception hierarchy for the P13 tool system."""

from __future__ import annotations


class P13Error(Exception):
    """Base class for all P13 application errors."""


class ToolRegistrationError(P13Error):
    """Raised at import/registration time when a tool fails a check.

    Example:
        ToolRegistrationError: Tool 'get_products' cannot be registered: missing description
    """


class ToolValidationError(P13Error):
    """Raised when Pydantic validation rejects a tool's input arguments."""


class ToolExecutionError(P13Error):
    """Raised when a tool handler encounters a runtime error."""


class ManifestMismatchError(P13Error):
    """Raised when the committed manifest differs from the generated manifest."""


class OllamaConnectionError(P13Error):
    """Raised when the Ollama server is unreachable."""
