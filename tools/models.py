"""
tools/models.py — Strict Pydantic input and output models for the three read tools.

Design rules enforced here
--------------------------
* ``extra="forbid"`` on every input model: any unknown argument raises
  ValidationError *before* the handler is called — a malformed argument never
  reaches a handler.
* Identifier patterns use ``[A-Za-z0-9...]`` (strict ASCII ranges).
  We deliberately do NOT use ``\\d``, which matches Devanagari, fullwidth, and
  other Unicode decimal digit categories.  See P13 trap note.
* Every result model carries ``truncated: bool`` and an optional
  ``truncation_warning`` so callers can detect row-limit enforcement.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------

class ToolInput(BaseModel):
    """Base class for all tool input models.

    Subclasses MUST NOT override ``model_config``'s ``extra`` setting;
    the registration decorator verifies that ``extra="forbid"`` is in
    effect at import time.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ToolOutput(BaseModel):
    """Base class for all tool output models."""

    model_config = ConfigDict(extra="forbid")
    truncated: bool = False
    truncation_warning: Optional[str] = None


# ---------------------------------------------------------------------------
# Tool 1 — search_documents
# ---------------------------------------------------------------------------

class SearchRequest(ToolInput):
    """Input model for the ``search_documents`` tool.

    Fields
    ------
    query:
        The free-text search string.  Must be between 1 and 512 characters.
    row_limit:
        Maximum number of rows to return.  Capped to 100.
    source_filter:
        Optional source namespace pattern — letters, digits, dots, hyphens,
        forward-slashes.  ASCII only; no ``\\d`` shorthand.
    """

    query: str = Field(..., min_length=1, max_length=512)
    row_limit: int = Field(default=20, ge=1, le=100)
    source_filter: Optional[str] = Field(
        default=None,
        pattern=r"^[A-Za-z0-9._/-]{1,128}$",
        description="Optional source namespace filter — ASCII alphanumeric, dots, hyphens, slashes.",
    )


class DocumentHit(ToolOutput):
    """A single document match returned by search."""

    id: str
    title: str
    snippet: str
    score: float
    source: str


class SearchResult(ToolOutput):
    """Output model for the ``search_documents`` tool."""

    hits: list[DocumentHit] = Field(default_factory=list)
    total_found: int = 0


# ---------------------------------------------------------------------------
# Tool 2 — lookup_document
# ---------------------------------------------------------------------------

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"
"""
Strict ASCII identifier pattern.

* Must start with a letter or digit.
* Subsequent characters: letters, digits, underscores, hyphens.
* Total length: 1–64 characters.

Why not ``\\d``?  The regex shorthand ``\\d`` in Python's ``re`` module (and
hence in Pydantic's pattern validator) matches any Unicode decimal digit, not
just ASCII 0-9.  That includes Devanagari digits (U+0966–U+096F), fullwidth
digits (U+FF10–U+FF19), and dozens of other scripts.  Using ``[0-9]`` (or the
equivalent ``[A-Za-z0-9]``) restricts matching to strict ASCII.
"""


class LookupRequest(ToolInput):
    """Input model for the ``lookup_document`` tool.

    Fields
    ------
    identifier:
        Document identifier.  Must match ``[A-Za-z0-9][A-Za-z0-9_-]{0,63}`` —
        ASCII only, 1 to 64 characters.
    fields:
        Optional whitelist of field names to return.  Each field name must
        match ``[A-Za-z0-9_]{1,64}``.
    row_limit:
        Maximum number of document fields to return.  For wide documents this
        prevents unbounded response payloads; the result carries
        ``truncated=True`` when the field count exceeds this limit.
    """

    identifier: str = Field(
        ...,
        pattern=_IDENTIFIER_PATTERN,
        description="ASCII identifier, 1–64 chars, letters/digits/underscores/hyphens.",
    )
    fields: Optional[list[str]] = Field(default=None)
    row_limit: int = Field(default=50, ge=1, le=500)

    @field_validator("fields", mode="before")
    @classmethod
    def validate_field_names(cls, v: Any) -> Any:
        """Each field name must be a plain ASCII identifier."""
        import re

        if v is None:
            return v
        field_pattern = re.compile(r"^[A-Za-z0-9_]{1,64}$")
        for name in v:
            if not field_pattern.match(str(name)):
                raise ValueError(
                    f"Field name {name!r} is invalid.  "
                    "Must match [A-Za-z0-9_]{{1,64}} (ASCII only)."
                )
        return v


class LookupResult(ToolOutput):
    """Output model for the ``lookup_document`` tool."""

    identifier: str
    data: dict[str, Any] = Field(default_factory=dict)
    found: bool = True


# ---------------------------------------------------------------------------
# Tool 3 — list_documents
# ---------------------------------------------------------------------------

_NAMESPACE_PATTERN = r"^[A-Za-z0-9._/-]{1,128}$"


class ListRequest(ToolInput):
    """Input model for the ``list_documents`` tool.

    Fields
    ------
    namespace:
        Source namespace to list.  Matches ``[A-Za-z0-9._/-]{1,128}``; ASCII only.
    cursor:
        Opaque pagination cursor from a previous ``ListResult``.
    row_limit:
        Maximum number of rows to return per page.  Capped to 200.
    """

    namespace: str = Field(
        ...,
        pattern=_NAMESPACE_PATTERN,
        description="Source namespace — ASCII alphanumeric, dots, hyphens, slashes.",
    )
    cursor: Optional[str] = Field(default=None, max_length=256)
    row_limit: int = Field(default=50, ge=1, le=200)


class DocumentSummary(ToolOutput):
    """A single document entry returned by list."""

    id: str
    title: str
    source: str


class ListResult(ToolOutput):
    """Output model for the ``list_documents`` tool."""

    items: list[DocumentSummary] = Field(default_factory=list)
    next_cursor: Optional[str] = None
    total_in_namespace: int = 0
