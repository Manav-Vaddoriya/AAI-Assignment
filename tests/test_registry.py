"""
tests/test_registry.py — Tests for the @register_tool decorator and its five checks.

Each of the five checks is tested by constructing a bad tool definition and
asserting that importing / registering it raises RegistrationError.

Because the registry is a module-level singleton we need to be careful about
state: each test that registers a dummy tool uses a unique function name and
cleans up the registry entry in a fixture teardown.
"""

import inspect
import pytest

from tools.models import ToolInput, SearchRequest
from tools.registry import (
    TOOL_REGISTRY,
    RegistrationError,
    register_tool,
)
from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cleanup(name: str):
    """Remove a test tool from the registry after the test."""
    TOOL_REGISTRY.pop(name, None)


# ---------------------------------------------------------------------------
# Check 1: non-empty docstring
# ---------------------------------------------------------------------------

class TestCheck1Docstring:
    def test_missing_docstring_raises(self):
        with pytest.raises(RegistrationError, match="docstring"):
            @register_tool
            def tool_no_doc(req: SearchRequest) -> None:
                pass

    def test_empty_docstring_raises(self):
        # inspect.getdoc strips and returns None for whitespace-only docs
        with pytest.raises(RegistrationError, match="docstring"):
            @register_tool
            def tool_empty_doc(req: SearchRequest) -> None:
                """"""
                pass

    def test_valid_docstring_passes(self):
        try:
            @register_tool
            def tool_with_doc(req: SearchRequest) -> None:
                """A valid one-line description."""
                pass
            assert "tool_with_doc" in TOOL_REGISTRY
        finally:
            _cleanup("tool_with_doc")


# ---------------------------------------------------------------------------
# Check 2: row_limit declared on the input model
# ---------------------------------------------------------------------------

class TestCheck2RowLimit:
    def test_model_without_row_limit_raises(self):
        class NoRowLimitInput(ToolInput):
            query: str

        with pytest.raises(RegistrationError, match="row_limit"):
            @register_tool
            def tool_no_row_limit(req: NoRowLimitInput) -> None:
                """This tool has no row_limit declared on its input model."""
                pass

    def test_model_with_row_limit_passes(self):
        """SearchRequest already has row_limit — should register fine."""
        try:
            @register_tool
            def tool_has_row_limit(req: SearchRequest) -> None:
                """Valid tool with a row_limit on its model."""
                pass
            assert TOOL_REGISTRY["tool_has_row_limit"].row_limit == 20
        finally:
            _cleanup("tool_has_row_limit")


# ---------------------------------------------------------------------------
# Check 3: first parameter must be a ToolInput subclass
# ---------------------------------------------------------------------------

class TestCheck3ToolInputSubclass:
    def test_plain_dict_annotation_raises(self):
        with pytest.raises(RegistrationError):
            @register_tool
            def tool_dict_input(req: dict) -> None:
                """Annotated with dict, not a ToolInput subclass."""
                pass

    def test_plain_pydantic_model_raises(self):
        """A plain BaseModel (not subclassing ToolInput) should fail check 3."""
        class PlainModel(BaseModel):
            query: str
            row_limit: int = 10

        with pytest.raises(RegistrationError):
            @register_tool
            def tool_plain_pydantic(req: PlainModel) -> None:
                """Plain Pydantic model, not a ToolInput subclass."""
                pass

    def test_no_annotation_raises(self):
        with pytest.raises(RegistrationError):
            @register_tool
            def tool_no_annotation(req) -> None:
                """No type annotation on the request parameter."""
                pass

    def test_tool_input_subclass_passes(self):
        try:
            @register_tool
            def tool_proper_input(req: SearchRequest) -> None:
                """SearchRequest is a ToolInput subclass — all good."""
                pass
            assert "tool_proper_input" in TOOL_REGISTRY
        finally:
            _cleanup("tool_proper_input")


# ---------------------------------------------------------------------------
# Check 4: input model must have extra="forbid"
# ---------------------------------------------------------------------------

class TestCheck4ExtraForbid:
    def test_extra_allow_raises(self):
        class AllowExtraInput(ToolInput):
            model_config = ConfigDict(extra="allow")
            query: str
            row_limit: int = 10

        with pytest.raises(RegistrationError, match="extra"):
            @register_tool
            def tool_extra_allow(req: AllowExtraInput) -> None:
                """Input model uses extra='allow' — must be rejected."""
                pass

    def test_extra_ignore_raises(self):
        class IgnoreExtraInput(ToolInput):
            model_config = ConfigDict(extra="ignore")
            query: str
            row_limit: int = 10

        with pytest.raises(RegistrationError, match="extra"):
            @register_tool
            def tool_extra_ignore(req: IgnoreExtraInput) -> None:
                """Input model uses extra='ignore' — must be rejected."""
                pass

    def test_extra_forbid_passes(self):
        """SearchRequest inherits extra='forbid' from ToolInput."""
        try:
            @register_tool
            def tool_extra_forbid(req: SearchRequest) -> None:
                """extra='forbid' is in effect via ToolInput — should pass."""
                pass
            assert "tool_extra_forbid" in TOOL_REGISTRY
        finally:
            _cleanup("tool_extra_forbid")


# ---------------------------------------------------------------------------
# Check 5: unique tool name
# ---------------------------------------------------------------------------

class TestCheck5UniqueName:
    def test_duplicate_registration_raises(self):
        try:
            @register_tool
            def tool_duplicate(req: SearchRequest) -> None:
                """First registration — valid."""
                pass

            with pytest.raises(RegistrationError, match="already registered"):
                @register_tool
                def tool_duplicate(req: SearchRequest) -> None:  # noqa: F811
                    """Second registration with the same name — must fail."""
                    pass
        finally:
            _cleanup("tool_duplicate")

    def test_different_names_both_pass(self):
        try:
            @register_tool
            def tool_unique_a(req: SearchRequest) -> None:
                """First unique tool."""
                pass

            @register_tool
            def tool_unique_b(req: SearchRequest) -> None:
                """Second unique tool."""
                pass

            assert "tool_unique_a" in TOOL_REGISTRY
            assert "tool_unique_b" in TOOL_REGISTRY
        finally:
            _cleanup("tool_unique_a")
            _cleanup("tool_unique_b")


# ---------------------------------------------------------------------------
# ToolEntry metadata
# ---------------------------------------------------------------------------

class TestToolEntry:
    def test_entry_has_correct_metadata(self):
        try:
            @register_tool
            def tool_metadata_check(req: SearchRequest) -> None:
                """Short description used as the manifest entry."""
                pass

            entry = TOOL_REGISTRY["tool_metadata_check"]
            assert entry.name == "tool_metadata_check"
            assert "Short description" in entry.description
            assert entry.input_model is SearchRequest
            assert entry.row_limit == 20
        finally:
            _cleanup("tool_metadata_check")
