"""
tests/test_app_registry.py — Registration decorator and registry tests.

Verifies all five import-time checks in @read_tool:
1. Non-empty description
2. Positive integer row_limit
3. First param annotated with a Pydantic BaseModel subclass
4. Input model has extra="forbid"
5. Unique tool name (no duplicates)
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict

from app.decorators import read_tool
from app.errors import ToolRegistrationError
from app.registry import TOOL_REGISTRY


# ---------------------------------------------------------------------------
# Minimal valid fixtures
# ---------------------------------------------------------------------------

class _ValidInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str


def _make_valid_handler(unique_suffix: str):
    """Return a new valid handler function with a unique name."""
    def handler(req: _ValidInput) -> dict:  # type: ignore[return]
        pass
    handler.__name__ = f"_test_valid_tool_{unique_suffix}"
    handler.__qualname__ = handler.__name__
    return handler


# ===========================================================================
# Check 1 — Description must be non-empty
# ===========================================================================

class TestCheck1Description:
    def test_empty_description_raises(self):
        with pytest.raises(ToolRegistrationError, match="missing description"):
            @read_tool(name="_test_empty_desc", description="", row_limit=10)
            def _handler(req: _ValidInput) -> dict:  # type: ignore[return]
                pass

    def test_whitespace_description_raises(self):
        with pytest.raises(ToolRegistrationError, match="missing description"):
            @read_tool(name="_test_ws_desc", description="   ", row_limit=10)
            def _handler(req: _ValidInput) -> dict:  # type: ignore[return]
                pass

    def test_non_string_description_raises(self):
        with pytest.raises(ToolRegistrationError, match="missing description"):
            @read_tool(name="_test_none_desc", description=None, row_limit=10)  # type: ignore[arg-type]
            def _handler(req: _ValidInput) -> dict:  # type: ignore[return]
                pass

    def test_valid_description_passes(self):
        name = "_test_check1_valid_desc"
        if name in TOOL_REGISTRY:
            del TOOL_REGISTRY[name]

        @read_tool(name=name, description="A valid description.", row_limit=10)
        def _handler(req: _ValidInput) -> dict:  # type: ignore[return]
            pass

        assert name in TOOL_REGISTRY
        del TOOL_REGISTRY[name]


# ===========================================================================
# Check 2 — row_limit must be a positive integer
# ===========================================================================

class TestCheck2RowLimit:
    def test_zero_row_limit_raises(self):
        with pytest.raises(ToolRegistrationError, match="row_limit"):
            @read_tool(name="_test_zero_rl", description="Valid desc", row_limit=0)
            def _handler(req: _ValidInput) -> dict:  # type: ignore[return]
                pass

    def test_negative_row_limit_raises(self):
        with pytest.raises(ToolRegistrationError, match="row_limit"):
            @read_tool(name="_test_neg_rl", description="Valid desc", row_limit=-5)
            def _handler(req: _ValidInput) -> dict:  # type: ignore[return]
                pass

    def test_string_row_limit_raises(self):
        with pytest.raises(ToolRegistrationError, match="row_limit"):
            @read_tool(name="_test_str_rl", description="Valid desc", row_limit="50")  # type: ignore[arg-type]
            def _handler(req: _ValidInput) -> dict:  # type: ignore[return]
                pass

    def test_none_row_limit_raises(self):
        with pytest.raises(ToolRegistrationError, match="row_limit"):
            @read_tool(name="_test_none_rl", description="Valid desc", row_limit=None)  # type: ignore[arg-type]
            def _handler(req: _ValidInput) -> dict:  # type: ignore[return]
                pass

    def test_valid_row_limit_passes(self):
        name = "_test_check2_valid_rl"
        if name in TOOL_REGISTRY:
            del TOOL_REGISTRY[name]

        @read_tool(name=name, description="Valid desc", row_limit=1)
        def _handler(req: _ValidInput) -> dict:  # type: ignore[return]
            pass

        assert TOOL_REGISTRY[name].row_limit == 1
        del TOOL_REGISTRY[name]


# ===========================================================================
# Check 3 — First param must be a Pydantic BaseModel subclass
# ===========================================================================

# Define these at module level so typing.get_type_hints() can resolve them
class _BadInputNoForbid(BaseModel):
    """A BaseModel subclass WITHOUT extra='forbid' — should fail Check 4."""
    value: str


class _AllowInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    value: str


class _IgnoreInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    value: str


class _DefaultInput(BaseModel):
    """No explicit extra config — defaults to 'ignore'."""
    value: str


class TestCheck3InputModel:
    def test_no_annotation_raises(self):
        with pytest.raises(ToolRegistrationError):
            @read_tool(name="_test_no_ann", description="Valid desc", row_limit=10)
            def _handler(req) -> dict:  # type: ignore[no-untyped-def, return]
                pass

    def test_plain_dict_annotation_raises(self):
        with pytest.raises(ToolRegistrationError):
            @read_tool(name="_test_dict_ann", description="Valid desc", row_limit=10)
            def _handler(req: dict) -> dict:  # type: ignore[return]
                pass

    def test_no_params_raises(self):
        with pytest.raises(ToolRegistrationError):
            @read_tool(name="_test_no_params", description="Valid desc", row_limit=10)
            def _handler() -> dict:  # type: ignore[return]
                pass

    def test_pydantic_model_without_forbid_fails_at_check4(self):
        """Check 3 accepts any BaseModel subclass; Check 4 rejects without extra='forbid'."""
        with pytest.raises(ToolRegistrationError, match="extra='forbid'"):
            @read_tool(name="_test_no_forbid2", description="Valid desc", row_limit=10)
            def _handler(req: _BadInputNoForbid) -> dict:  # type: ignore[return]
                pass

    def test_valid_input_model_passes(self):
        name = "_test_check3_valid"
        if name in TOOL_REGISTRY:
            del TOOL_REGISTRY[name]

        @read_tool(name=name, description="Valid desc", row_limit=5)
        def _handler(req: _ValidInput) -> dict:  # type: ignore[return]
            pass

        assert TOOL_REGISTRY[name].input_model is _ValidInput
        del TOOL_REGISTRY[name]


# ===========================================================================
# Check 4 — Input model must have extra="forbid"
# ===========================================================================

class TestCheck4ExtraForbid:
    def test_extra_allow_raises(self):
        with pytest.raises(ToolRegistrationError, match="extra='forbid'"):
            @read_tool(name="_test_extra_allow2", description="Valid desc", row_limit=10)
            def _handler(req: _AllowInput) -> dict:  # type: ignore[return]
                pass

    def test_extra_ignore_raises(self):
        with pytest.raises(ToolRegistrationError, match="extra='forbid'"):
            @read_tool(name="_test_extra_ignore2", description="Valid desc", row_limit=10)
            def _handler(req: _IgnoreInput) -> dict:  # type: ignore[return]
                pass

    def test_no_extra_config_raises(self):
        with pytest.raises(ToolRegistrationError, match="extra='forbid'"):
            @read_tool(name="_test_no_extra_cfg2", description="Valid desc", row_limit=10)
            def _handler(req: _DefaultInput) -> dict:  # type: ignore[return]
                pass

    def test_extra_forbid_passes(self):
        name = "_test_check4_forbid"
        if name in TOOL_REGISTRY:
            del TOOL_REGISTRY[name]

        @read_tool(name=name, description="Valid desc", row_limit=10)
        def _handler(req: _ValidInput) -> dict:  # type: ignore[return]
            pass

        assert name in TOOL_REGISTRY
        del TOOL_REGISTRY[name]


# ===========================================================================
# Check 5 — Tool name must be unique
# ===========================================================================

class TestCheck5UniqueName:
    def test_duplicate_name_raises(self):
        name = "_test_duplicate_name"
        if name in TOOL_REGISTRY:
            del TOOL_REGISTRY[name]

        # First registration should succeed
        @read_tool(name=name, description="First", row_limit=10)
        def _handler1(req: _ValidInput) -> dict:  # type: ignore[return]
            pass

        # Second registration with same name must fail
        with pytest.raises(ToolRegistrationError, match="already exists"):
            @read_tool(name=name, description="Second", row_limit=10)
            def _handler2(req: _ValidInput) -> dict:  # type: ignore[return]
                pass

        del TOOL_REGISTRY[name]

    def test_different_names_both_register(self):
        name_a = "_test_unique_a"
        name_b = "_test_unique_b"
        for n in (name_a, name_b):
            if n in TOOL_REGISTRY:
                del TOOL_REGISTRY[n]

        @read_tool(name=name_a, description="Tool A", row_limit=10)
        def _handler_a(req: _ValidInput) -> dict:  # type: ignore[return]
            pass

        @read_tool(name=name_b, description="Tool B", row_limit=10)
        def _handler_b(req: _ValidInput) -> dict:  # type: ignore[return]
            pass

        assert name_a in TOOL_REGISTRY
        assert name_b in TOOL_REGISTRY
        del TOOL_REGISTRY[name_a]
        del TOOL_REGISTRY[name_b]


# ===========================================================================
# Registry contents (production tools)
# ===========================================================================

class TestProductionRegistry:
    """Verify the three production tools are correctly registered."""

    def setup_method(self):
        # Ensure production handlers are imported
        import app.handlers  # noqa: F401, PLC0415

    def test_three_tools_registered(self):
        prod_tools = [k for k in TOOL_REGISTRY if not k.startswith("_test")]
        assert len(prod_tools) == 3

    def test_get_product_registered(self):
        assert "get_product" in TOOL_REGISTRY

    def test_get_user_registered(self):
        assert "get_user" in TOOL_REGISTRY

    def test_get_user_orders_registered(self):
        assert "get_user_orders" in TOOL_REGISTRY

    def test_all_tools_read_only(self):
        for name, entry in TOOL_REGISTRY.items():
            if name.startswith("_test"):
                continue
            assert entry.read_only is True, f"{name} is not marked read_only"

    def test_all_tools_have_descriptions(self):
        for name, entry in TOOL_REGISTRY.items():
            if name.startswith("_test"):
                continue
            assert entry.description.strip(), f"{name} has empty description"

    def test_all_tools_have_positive_row_limits(self):
        for name, entry in TOOL_REGISTRY.items():
            if name.startswith("_test"):
                continue
            assert entry.row_limit >= 1, f"{name} has non-positive row_limit"
