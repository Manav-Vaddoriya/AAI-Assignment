"""
tests/test_tools.py — Integration tests for the three read tool handlers.

Covers
------
* search_documents: keyword matching, source filtering, truncation flag.
* lookup_document: found / not-found, field filtering, identifier rejection.
* list_documents: pagination, cursor continuity, truncation flag.
"""

import pytest
from pydantic import ValidationError

from tools.handlers import list_documents, lookup_document, search_documents
from tools.models import ListRequest, LookupRequest, SearchRequest


# ---------------------------------------------------------------------------
# search_documents
# ---------------------------------------------------------------------------

class TestSearchDocuments:
    def test_returns_hits_for_known_keyword(self):
        req = SearchRequest(query="retrieval")
        result = search_documents(req)
        assert len(result.hits) >= 1
        assert any("retrieval" in h.title.lower() for h in result.hits)

    def test_empty_query_rejected_before_handler(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="")

    def test_extra_arg_rejected_before_handler(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="test", surprise="boom")

    def test_truncation_flag_set_when_results_exceed_row_limit(self):
        # Use a very broad query and row_limit=1 to force truncation
        req = SearchRequest(query="document", row_limit=1)
        result = search_documents(req)
        # With 20 mock docs all matching "document", total_found > 1
        if result.total_found > 1:
            assert result.truncated is True
            assert result.truncation_warning is not None
            assert len(result.hits) == 1
        else:
            # If somehow only 1 match, truncation should be False
            assert result.truncated is False

    def test_no_truncation_when_results_within_limit(self):
        req = SearchRequest(query="retrieval", row_limit=100)
        result = search_documents(req)
        assert result.truncated is False
        assert result.truncation_warning is None

    def test_source_filter_narrows_results(self):
        req = SearchRequest(query="document", source_filter="corpus/governance")
        result = search_documents(req)
        for hit in result.hits:
            assert hit.source.startswith("corpus/governance")

    def test_source_filter_no_match_returns_empty(self):
        req = SearchRequest(query="document", source_filter="corpus/nonexistent")
        result = search_documents(req)
        assert result.hits == []
        assert result.total_found == 0

    def test_result_fields_populated(self):
        req = SearchRequest(query="pydantic")
        result = search_documents(req)
        if result.hits:
            hit = result.hits[0]
            assert hit.id
            assert hit.title
            assert hit.snippet
            assert 0.0 <= hit.score <= 1.0
            assert hit.source


# ---------------------------------------------------------------------------
# lookup_document
# ---------------------------------------------------------------------------

class TestLookupDocument:
    def test_known_identifier_returns_document(self):
        req = LookupRequest(identifier="doc-0001")
        result = lookup_document(req)
        assert result.found is True
        assert result.identifier == "doc-0001"
        assert "title" in result.data

    def test_unknown_identifier_returns_not_found(self):
        req = LookupRequest(identifier="doc-ZZZZ")
        result = lookup_document(req)
        assert result.found is False
        assert result.data == {}

    def test_field_filter_returns_only_requested_fields(self):
        req = LookupRequest(identifier="doc-0001", fields=["title", "source"])
        result = lookup_document(req)
        assert result.found is True
        assert set(result.data.keys()) == {"title", "source"}

    def test_invalid_identifier_rejected_before_handler(self):
        """Pattern enforcement: space in identifier."""
        with pytest.raises(ValidationError):
            LookupRequest(identifier="bad id")

    def test_devanagari_digit_rejected(self):
        """P13 trap: \\d would allow Devanagari; [0-9] must not."""
        with pytest.raises(ValidationError):
            LookupRequest(identifier="doc१")

    def test_fullwidth_digit_rejected(self):
        with pytest.raises(ValidationError):
            LookupRequest(identifier="doc１")

    def test_extra_arg_rejected_before_handler(self):
        with pytest.raises(ValidationError):
            LookupRequest(identifier="doc-0001", extra_field="bad")

    def test_invalid_field_name_rejected(self):
        with pytest.raises(ValidationError):
            LookupRequest(identifier="doc-0001", fields=["bad field!"])


# ---------------------------------------------------------------------------
# list_documents
# ---------------------------------------------------------------------------

class TestListDocuments:
    def test_returns_items_in_namespace(self):
        req = ListRequest(namespace="corpus/engineering")
        result = list_documents(req)
        assert len(result.items) >= 1
        for item in result.items:
            assert item.source.startswith("corpus/engineering")

    def test_row_limit_respected(self):
        req = ListRequest(namespace="corpus/engineering", row_limit=2)
        result = list_documents(req)
        assert len(result.items) <= 2

    def test_truncation_flag_and_cursor_provided_when_more_results(self):
        req = ListRequest(namespace="corpus/engineering", row_limit=1)
        result = list_documents(req)
        # Engineering namespace has several docs
        if result.total_in_namespace > 1:
            assert result.truncated is True
            assert result.next_cursor is not None
            assert result.truncation_warning is not None

    def test_cursor_pagination_continues_from_correct_offset(self):
        # Page 1
        req1 = ListRequest(namespace="corpus/engineering", row_limit=2)
        page1 = list_documents(req1)

        if page1.next_cursor is None:
            pytest.skip("Not enough docs for pagination test")

        # Page 2
        req2 = ListRequest(namespace="corpus/engineering", row_limit=2, cursor=page1.next_cursor)
        page2 = list_documents(req2)

        ids_page1 = {item.id for item in page1.items}
        ids_page2 = {item.id for item in page2.items}
        # Pages must not overlap
        assert ids_page1.isdisjoint(ids_page2)

    def test_no_truncation_when_all_results_fit(self):
        req = ListRequest(namespace="corpus/engineering", row_limit=200)
        result = list_documents(req)
        assert result.truncated is False
        assert result.next_cursor is None

    def test_empty_namespace_returns_empty(self):
        req = ListRequest(namespace="corpus/nonexistent")
        result = list_documents(req)
        assert result.items == []
        assert result.total_in_namespace == 0
        assert result.truncated is False

    def test_extra_arg_rejected_before_handler(self):
        with pytest.raises(ValidationError):
            ListRequest(namespace="corpus/eng", rogue="x")

    def test_invalid_namespace_rejected(self):
        with pytest.raises(ValidationError):
            ListRequest(namespace="corpus/héllo")
