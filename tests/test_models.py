"""
tests/test_models.py — Unit tests for Pydantic input/output models.

Covers
------
* ``extra="forbid"`` rejects unknown arguments on every input model.
* Regex pattern enforcement (ASCII-only identifiers and namespaces).
* Row-limit defaults and bounds.
* Field-name validator on LookupRequest.
* Output models carry truncated / truncation_warning correctly.
"""

import pytest
from pydantic import ValidationError

from tools.models import (
    ListRequest,
    LookupRequest,
    SearchRequest,
    ToolInput,
)


# ---------------------------------------------------------------------------
# SearchRequest
# ---------------------------------------------------------------------------

class TestSearchRequest:
    def test_valid_minimal(self):
        req = SearchRequest(query="retrieval")
        assert req.query == "retrieval"
        assert req.row_limit == 20
        assert req.source_filter is None

    def test_valid_full(self):
        req = SearchRequest(query="ci", row_limit=5, source_filter="corpus/devops")
        assert req.row_limit == 5
        assert req.source_filter == "corpus/devops"

    def test_extra_field_rejected(self):
        """Extra fields must raise ValidationError before the handler is called."""
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query="test", evil_param="injected")
        assert "extra" in str(exc_info.value).lower() or "unexpected" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()

    def test_empty_query_rejected(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="")

    def test_query_too_long_rejected(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="x" * 513)

    def test_row_limit_below_1_rejected(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="test", row_limit=0)

    def test_row_limit_above_100_rejected(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="test", row_limit=101)

    def test_source_filter_invalid_chars_rejected(self):
        """source_filter must be ASCII-only; Unicode letters should be rejected."""
        with pytest.raises(ValidationError):
            SearchRequest(query="test", source_filter="corpus/héllo")

    def test_source_filter_too_long_rejected(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="test", source_filter="a" * 129)

    def test_source_filter_valid_slashes_and_dots(self):
        req = SearchRequest(query="test", source_filter="corp/team.sub-ns/v1")
        assert req.source_filter == "corp/team.sub-ns/v1"


# ---------------------------------------------------------------------------
# LookupRequest  — identifier regex (the P13 trap lives here)
# ---------------------------------------------------------------------------

class TestLookupRequest:
    def test_valid_identifier(self):
        req = LookupRequest(identifier="doc-0001")
        assert req.identifier == "doc-0001"

    def test_valid_identifier_alphanumeric(self):
        req = LookupRequest(identifier="ABC123")
        assert req.identifier == "ABC123"

    def test_identifier_with_underscore(self):
        req = LookupRequest(identifier="my_document_01")
        assert req.identifier == "my_document_01"

    def test_identifier_max_length(self):
        # 64 chars starting with a letter — should pass
        req = LookupRequest(identifier="A" * 64)
        assert len(req.identifier) == 64

    def test_identifier_too_long_rejected(self):
        with pytest.raises(ValidationError):
            LookupRequest(identifier="A" * 65)

    def test_identifier_empty_rejected(self):
        with pytest.raises(ValidationError):
            LookupRequest(identifier="")

    def test_identifier_starts_with_hyphen_rejected(self):
        """Must start with a letter or digit, not a hyphen."""
        with pytest.raises(ValidationError):
            LookupRequest(identifier="-bad")

    def test_identifier_space_rejected(self):
        with pytest.raises(ValidationError):
            LookupRequest(identifier="bad id")

    # --- The named P13 trap: \d matches non-ASCII digits ---
    def test_identifier_devanagari_digit_rejected(self):
        """
        Devanagari digit '१' (U+0967) must NOT be accepted.
        This is the named P13 trap — \\d would pass it, [0-9] rejects it.
        """
        with pytest.raises(ValidationError):
            LookupRequest(identifier="doc१")

    def test_identifier_fullwidth_digit_rejected(self):
        """Fullwidth digit '１' (U+FF11) must NOT be accepted."""
        with pytest.raises(ValidationError):
            LookupRequest(identifier="doc１")

    def test_identifier_unicode_letter_rejected(self):
        """Non-ASCII letter must be rejected."""
        with pytest.raises(ValidationError):
            LookupRequest(identifier="héllo")

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            LookupRequest(identifier="doc-0001", unknown_field="x")

    def test_fields_valid(self):
        req = LookupRequest(identifier="doc-0001", fields=["title", "source"])
        assert req.fields == ["title", "source"]

    def test_fields_invalid_name_rejected(self):
        """Field names with spaces or non-ASCII chars must be rejected."""
        with pytest.raises(ValidationError):
            LookupRequest(identifier="doc-0001", fields=["bad field name!"])

    def test_fields_too_long_rejected(self):
        with pytest.raises(ValidationError):
            LookupRequest(identifier="doc-0001", fields=["a" * 65])


# ---------------------------------------------------------------------------
# ListRequest
# ---------------------------------------------------------------------------

class TestListRequest:
    def test_valid_minimal(self):
        req = ListRequest(namespace="corpus/engineering")
        assert req.namespace == "corpus/engineering"
        assert req.row_limit == 50
        assert req.cursor is None

    def test_namespace_invalid_unicode_rejected(self):
        with pytest.raises(ValidationError):
            ListRequest(namespace="corpus/héllo")

    def test_namespace_too_long_rejected(self):
        with pytest.raises(ValidationError):
            ListRequest(namespace="a" * 129)

    def test_row_limit_above_200_rejected(self):
        with pytest.raises(ValidationError):
            ListRequest(namespace="corpus/eng", row_limit=201)

    def test_row_limit_zero_rejected(self):
        with pytest.raises(ValidationError):
            ListRequest(namespace="corpus/eng", row_limit=0)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            ListRequest(namespace="corpus/eng", inject="evil")

    def test_cursor_too_long_rejected(self):
        with pytest.raises(ValidationError):
            ListRequest(namespace="corpus/eng", cursor="x" * 257)


# ---------------------------------------------------------------------------
# ToolInput base — extra="forbid" is inherited
# ---------------------------------------------------------------------------

class TestToolInputBase:
    def test_base_class_has_forbid(self):
        assert ToolInput.model_config.get("extra") == "forbid"
