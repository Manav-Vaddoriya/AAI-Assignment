"""
tests/test_app_models.py — Schema validation tests for app/schemas.py

Covers:
- Valid/invalid product IDs (ASCII, Unicode digits, fullwidth, Devanagari)
- Valid/invalid user IDs
- extra="forbid" on all models
- Row limit validation (ge, le constraints)
- Missing required fields
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import ProductInput, UserInput, UserOrdersInput


# ===========================================================================
# ProductInput tests
# ===========================================================================

class TestProductInput:
    """Validation tests for ProductInput."""

    def test_valid_product_id(self):
        m = ProductInput(product_id="P1001")
        assert m.product_id == "P1001"

    def test_valid_product_id_large_number(self):
        m = ProductInput(product_id="P9999999")
        assert m.product_id == "P9999999"

    def test_valid_product_id_single_digit(self):
        m = ProductInput(product_id="P1")
        assert m.product_id == "P1"

    def test_invalid_product_id_no_prefix(self):
        with pytest.raises(ValidationError):
            ProductInput(product_id="1001")

    def test_invalid_product_id_lowercase_prefix(self):
        with pytest.raises(ValidationError):
            ProductInput(product_id="p1001")

    def test_invalid_product_id_alpha_digits(self):
        with pytest.raises(ValidationError):
            ProductInput(product_id="PABC")

    def test_invalid_product_id_devanagari_digits(self):
        """Devanagari digits (\\d matches but [0-9] does not) must be rejected."""
        with pytest.raises(ValidationError):
            ProductInput(product_id="P१२३")

    def test_invalid_product_id_fullwidth_digits(self):
        """Fullwidth digits (U+FF11–U+FF19) must be rejected."""
        with pytest.raises(ValidationError):
            ProductInput(product_id="P１２３")

    def test_invalid_product_id_empty_string(self):
        with pytest.raises(ValidationError):
            ProductInput(product_id="")

    def test_invalid_product_id_only_P(self):
        """'P' with no digits is invalid."""
        with pytest.raises(ValidationError):
            ProductInput(product_id="P")

    def test_extra_field_rejected(self):
        """extra='forbid' — unknown fields must raise ValidationError."""
        with pytest.raises(ValidationError):
            ProductInput(product_id="P1001", admin=True)

    def test_extra_field_never_reaches_handler(self):
        """Prove that extra fields are blocked before handler is called."""
        handler_called = False

        def fake_handler(req: ProductInput) -> None:
            nonlocal handler_called
            handler_called = True

        with pytest.raises(ValidationError):
            fake_handler(ProductInput.model_validate({"product_id": "P1001", "delete_database": True}))

        assert handler_called is False

    def test_missing_product_id_rejected(self):
        with pytest.raises(ValidationError):
            ProductInput()  # type: ignore[call-arg]

    def test_model_config_extra_forbid(self):
        assert ProductInput.model_config.get("extra") == "forbid"


# ===========================================================================
# UserInput tests
# ===========================================================================

class TestUserInput:
    """Validation tests for UserInput."""

    def test_valid_user_id(self):
        m = UserInput(user_id="U1001")
        assert m.user_id == "U1001"

    def test_valid_user_id_large_number(self):
        m = UserInput(user_id="U9999")
        assert m.user_id == "U9999"

    def test_invalid_user_id_wrong_prefix(self):
        with pytest.raises(ValidationError):
            UserInput(user_id="P1001")

    def test_invalid_user_id_lowercase(self):
        with pytest.raises(ValidationError):
            UserInput(user_id="u1001")

    def test_invalid_user_id_devanagari_digits(self):
        """U + Devanagari digits must be rejected."""
        with pytest.raises(ValidationError):
            UserInput(user_id="U१२३")

    def test_invalid_user_id_fullwidth_digits(self):
        with pytest.raises(ValidationError):
            UserInput(user_id="U１２３")

    def test_invalid_user_id_alpha(self):
        with pytest.raises(ValidationError):
            UserInput(user_id="UABC")

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            UserInput(user_id="U1001", role="admin")

    def test_missing_user_id_rejected(self):
        with pytest.raises(ValidationError):
            UserInput()  # type: ignore[call-arg]

    def test_model_config_extra_forbid(self):
        assert UserInput.model_config.get("extra") == "forbid"


# ===========================================================================
# UserOrdersInput tests
# ===========================================================================

class TestUserOrdersInput:
    """Validation tests for UserOrdersInput."""

    def test_valid_minimal(self):
        m = UserOrdersInput(user_id="U1001")
        assert m.user_id == "U1001"
        assert m.limit == 20  # default

    def test_valid_custom_limit(self):
        m = UserOrdersInput(user_id="U1001", limit=5)
        assert m.limit == 5

    def test_limit_at_maximum(self):
        m = UserOrdersInput(user_id="U1001", limit=100)
        assert m.limit == 100

    def test_limit_at_minimum(self):
        m = UserOrdersInput(user_id="U1001", limit=1)
        assert m.limit == 1

    def test_limit_below_minimum_rejected(self):
        with pytest.raises(ValidationError):
            UserOrdersInput(user_id="U1001", limit=0)

    def test_limit_zero_rejected(self):
        with pytest.raises(ValidationError):
            UserOrdersInput(user_id="U1001", limit=0)

    def test_limit_negative_rejected(self):
        with pytest.raises(ValidationError):
            UserOrdersInput(user_id="U1001", limit=-1)

    def test_limit_above_maximum_rejected(self):
        """The LLM requesting 1,000,000 rows must be rejected."""
        with pytest.raises(ValidationError):
            UserOrdersInput(user_id="U1001", limit=1_000_000)

    def test_limit_above_100_rejected(self):
        with pytest.raises(ValidationError):
            UserOrdersInput(user_id="U1001", limit=101)

    def test_invalid_user_id_rejected(self):
        with pytest.raises(ValidationError):
            UserOrdersInput(user_id="INVALID", limit=10)

    def test_devanagari_user_id_rejected(self):
        with pytest.raises(ValidationError):
            UserOrdersInput(user_id="U१२३", limit=10)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            UserOrdersInput(user_id="U1001", limit=10, sql="DROP TABLE orders")

    def test_missing_user_id_rejected(self):
        with pytest.raises(ValidationError):
            UserOrdersInput(limit=10)  # type: ignore[call-arg]

    def test_model_config_extra_forbid(self):
        assert UserOrdersInput.model_config.get("extra") == "forbid"
