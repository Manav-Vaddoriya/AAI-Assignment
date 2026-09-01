"""
tools/handlers.py — Three typed read tools registered at import time.

Each handler
------------
* Accepts a single Pydantic input model (validated before handler is called).
* Enforces its own ``row_limit``, sets ``truncated=True`` and populates
  ``truncation_warning`` when results are trimmed.
* Is decorated with ``@register_tool``, which runs five checks at import time
  and adds the tool to ``TOOL_REGISTRY``.

Backends
--------
The implementations below use deterministic in-memory mock data so the module
is self-contained and fully testable without a database.  The typing contracts
(input validation, row limits, truncation flags) are the same regardless of
the backend; swapping in a real database is a matter of replacing the body of
each ``_backend_*`` helper.
"""

from __future__ import annotations

import hashlib
from typing import Any

from tools.models import (
    DocumentHit,
    DocumentSummary,
    ListRequest,
    ListResult,
    LookupRequest,
    LookupResult,
    SearchRequest,
    SearchResult,
)
from tools.registry import register_tool

# ---------------------------------------------------------------------------
# In-memory mock data store
# ---------------------------------------------------------------------------

_DOCUMENTS: list[dict[str, Any]] = [
    {
        "id": f"doc-{i:04d}",
        "title": f"Document {i}: {topic}",
        "source": f"corpus/{namespace}",
        "content": f"This is the body of document {i} about {topic}. " * 5,
        "score": round(1.0 - i * 0.01, 4),
    }
    for i, (topic, namespace) in enumerate(
        [
            ("retrieval systems", "engineering"),
            ("pydantic validation", "engineering"),
            ("CI pipelines", "devops"),
            ("row limits", "engineering"),
            ("manifest generation", "devops"),
            ("typed adapters", "engineering"),
            ("schema fuzzing", "qa"),
            ("ledger integrity", "governance"),
            ("entitlement rules", "governance"),
            ("cost metering", "observability"),
            ("prompt versioning", "engineering"),
            ("token exchange", "security"),
            ("rank fusion", "engineering"),
            ("canary tools", "qa"),
            ("audit logging", "governance"),
            ("idempotency store", "engineering"),
            ("compensation sagas", "engineering"),
            ("durable execution", "engineering"),
            ("permission matrix", "governance"),
            ("answer contract", "engineering"),
        ],
        start=1,
    )
]

_DOC_BY_ID: dict[str, dict[str, Any]] = {d["id"]: d for d in _DOCUMENTS}


# ---------------------------------------------------------------------------
# Tool 1: search_documents
# ---------------------------------------------------------------------------


@register_tool
def search_documents(req: SearchRequest) -> SearchResult:
    """Search documents by keyword query.

    Returns up to ``row_limit`` matching documents from the corpus, ranked by
    relevance score.  When the total matches exceed ``row_limit`` the result
    carries ``truncated=True`` and a human-readable ``truncation_warning``.

    Parameters
    ----------
    req:
        A validated ``SearchRequest``.  Extra fields are rejected before this
        function is called.

    Returns
    -------
    SearchResult
        Ranked list of ``DocumentHit`` objects plus ``truncated`` / ``total_found``.
    """
    query_lower = req.query.lower()

    # Filter by source namespace if provided
    candidates = _DOCUMENTS
    if req.source_filter:
        prefix = req.source_filter.rstrip("/")
        candidates = [d for d in candidates if d["source"].startswith(prefix)]

    # Simple keyword match (real backend would use full-text search)
    matched = [
        d
        for d in candidates
        if query_lower in d["title"].lower() or query_lower in d["content"].lower()
    ]

    total_found = len(matched)
    truncated = total_found > req.row_limit
    page = matched[: req.row_limit]

    hits = [
        DocumentHit(
            id=d["id"],
            title=d["title"],
            snippet=d["content"][:120] + "…",
            score=d["score"],
            source=d["source"],
            truncated=False,
        )
        for d in page
    ]

    return SearchResult(
        hits=hits,
        total_found=total_found,
        truncated=truncated,
        truncation_warning=(
            f"Results truncated to {req.row_limit} of {total_found} matches. "
            "Use a narrower query or source_filter to reduce the result set."
        )
        if truncated
        else None,
    )


# ---------------------------------------------------------------------------
# Tool 2: lookup_document
# ---------------------------------------------------------------------------


@register_tool
def lookup_document(req: LookupRequest) -> LookupResult:
    """Look up a single document by its unique identifier.

    Returns the document's fields.  If ``fields`` is specified, only those
    named keys are returned.  The identifier must match the strict ASCII
    pattern ``[A-Za-z0-9][A-Za-z0-9_-]{0,63}``; Pydantic enforces this
    before the handler is called.

    Parameters
    ----------
    req:
        A validated ``LookupRequest``.

    Returns
    -------
    LookupResult
        The document data (or ``found=False`` if the identifier is unknown).
    """
    doc = _DOC_BY_ID.get(req.identifier)

    if doc is None:
        return LookupResult(
            identifier=req.identifier,
            data={},
            found=False,
        )

    data = dict(doc)
    if req.fields:
        data = {k: v for k, v in data.items() if k in req.fields}

    # Enforce row_limit on number of fields returned (for wide documents)
    all_keys = list(data.keys())
    truncated = len(all_keys) > req.row_limit
    if truncated:
        data = {k: data[k] for k in all_keys[: req.row_limit]}

    return LookupResult(
        identifier=req.identifier,
        data=data,
        found=True,
        truncated=truncated,
        truncation_warning=(
            f"Response truncated to {req.row_limit} of {len(all_keys)} fields. "
            "Use the 'fields' parameter to select specific fields."
        )
        if truncated
        else None,
    )


# ---------------------------------------------------------------------------
# Tool 3: list_documents
# ---------------------------------------------------------------------------

_PAGE_SIZE_SENTINEL = object()


@register_tool
def list_documents(req: ListRequest) -> ListResult:
    """List documents within a namespace, with cursor-based pagination.

    Returns up to ``row_limit`` document summaries.  When there are more
    documents in the namespace the response includes a ``next_cursor`` and sets
    ``truncated=True``.

    Cursor format: an opaque base-16 offset string derived from the start
    index.  The cursor is stable as long as the document set does not change.

    Parameters
    ----------
    req:
        A validated ``ListRequest``.  ``namespace`` must be ASCII only.

    Returns
    -------
    ListResult
        Page of ``DocumentSummary`` objects plus pagination metadata.
    """
    prefix = req.namespace.rstrip("/")
    namespace_docs = [d for d in _DOCUMENTS if d["source"].startswith(prefix)]

    total = len(namespace_docs)

    # Decode cursor (hex-encoded integer offset)
    offset = 0
    if req.cursor:
        try:
            offset = int(req.cursor, 16)
        except ValueError:
            offset = 0

    page_docs = namespace_docs[offset : offset + req.row_limit]
    next_offset = offset + req.row_limit
    has_more = next_offset < total

    items = [
        DocumentSummary(
            id=d["id"],
            title=d["title"],
            source=d["source"],
        )
        for d in page_docs
    ]

    return ListResult(
        items=items,
        next_cursor=format(next_offset, "x") if has_more else None,
        total_in_namespace=total,
        truncated=has_more,
        truncation_warning=(
            f"Page truncated to {req.row_limit} of {total - offset} remaining items "
            f"in namespace '{prefix}'.  Use next_cursor to continue pagination."
        )
        if has_more
        else None,
    )
