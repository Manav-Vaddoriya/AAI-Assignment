"""
tools package — typed read tools with strict input models and a manifest generator.
"""
from tools.registry import TOOL_REGISTRY, RegistrationError, register_tool
from tools.models import (
    SearchRequest,
    SearchResult,
    LookupRequest,
    LookupResult,
    ListRequest,
    ListResult,
)

__all__ = [
    "TOOL_REGISTRY",
    "RegistrationError",
    "register_tool",
    "SearchRequest",
    "SearchResult",
    "LookupRequest",
    "LookupResult",
    "ListRequest",
    "ListResult",
]
