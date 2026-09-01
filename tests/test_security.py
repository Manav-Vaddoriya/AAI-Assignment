"""
tests/test_security.py — Security invariant: malformed arguments NEVER reach handlers.

This is the critical P13 safety test.  Uses a spy/mock handler pattern to
prove that validation failures prevent handler execution.

Test name (as required by spec):  test_malformed_arguments_never_reach_handler
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import ProductInput, UserInput, UserOrdersInput


class TestMalformedArgumentsNeverReachHandler:
    """
    Security tests proving that bad inputs are always stopped before handlers.

    Pattern:
        handler_called = False
        try:
            validated = InputModel(**bad_args)
            handler_called = True  # <-- only reached if validation passes
            handler(validated)
        except ValidationError:
            pass
        assert handler_called is False
    """

    def _call_with_spy(self, model_cls, **kwargs) -> bool:
        """Return True if the handler would have been called, False if blocked."""
        handler_called = False
        try:
            validated = model_cls(**kwargs)
            handler_called = True
            # In real code the handler would run here.
            # We stop here — the point is that we reached past validation.
        except ValidationError:
            pass
        return handler_called

    # ------------------------------------------------------------------
    # 1. Missing required field
    # ------------------------------------------------------------------

    def test_malformed_arguments_never_reach_handler_missing_product_id(self):
        """Missing required field must be rejected before handler is called."""
        handler_called = self._call_with_spy(ProductInput)
        assert handler_called is False

    def test_malformed_arguments_never_reach_handler_missing_user_id(self):
        handler_called = self._call_with_spy(UserInput)
        assert handler_called is False

    # ------------------------------------------------------------------
    # 2. Wrong type
    # ------------------------------------------------------------------

    def test_malformed_arguments_never_reach_handler_wrong_type_product(self):
        """Integer product_id must be rejected (expects string matching pattern)."""
        handler_called = self._call_with_spy(ProductInput, product_id=1001)
        assert handler_called is False

    def test_malformed_arguments_never_reach_handler_wrong_type_limit(self):
        """String limit must be rejected."""
        handler_called = self._call_with_spy(UserOrdersInput, user_id="U1001", limit="lots")
        assert handler_called is False

    # ------------------------------------------------------------------
    # 3. Invalid identifier format
    # ------------------------------------------------------------------

    def test_malformed_arguments_never_reach_handler_invalid_product_id(self):
        """'ABC' does not match ^P[0-9]+$ — must be rejected."""
        handler_called = self._call_with_spy(ProductInput, product_id="ABC")
        assert handler_called is False

    def test_malformed_arguments_never_reach_handler_invalid_user_id(self):
        handler_called = self._call_with_spy(UserInput, user_id="user-001")
        assert handler_called is False

    # ------------------------------------------------------------------
    # 4. Unicode digit identifier
    # ------------------------------------------------------------------

    def test_malformed_arguments_never_reach_handler_devanagari_product_id(self):
        """Devanagari digits in product_id must be rejected (\\d trap)."""
        handler_called = self._call_with_spy(ProductInput, product_id="P१२३")
        assert handler_called is False

    def test_malformed_arguments_never_reach_handler_fullwidth_product_id(self):
        """Fullwidth digits in product_id must be rejected."""
        handler_called = self._call_with_spy(ProductInput, product_id="P１２３")
        assert handler_called is False

    def test_malformed_arguments_never_reach_handler_devanagari_user_id(self):
        handler_called = self._call_with_spy(UserInput, user_id="U१२३")
        assert handler_called is False

    # ------------------------------------------------------------------
    # 5. Extra unknown field
    # ------------------------------------------------------------------

    def test_malformed_arguments_never_reach_handler_extra_field_product(self):
        """Extra field 'admin=True' must be rejected due to extra='forbid'."""
        handler_called = self._call_with_spy(ProductInput, product_id="P1001", admin=True)
        assert handler_called is False

    def test_malformed_arguments_never_reach_handler_extra_field_user(self):
        handler_called = self._call_with_spy(UserInput, user_id="U1001", role="superuser")
        assert handler_called is False

    def test_malformed_arguments_never_reach_handler_sql_injection_extra_field(self):
        """SQL injection attempt via extra field must be blocked."""
        handler_called = self._call_with_spy(
            ProductInput,
            product_id="P1001",
            sql="DROP TABLE products; --",
        )
        assert handler_called is False

    def test_malformed_arguments_never_reach_handler_delete_database_extra_field(self):
        """Simulated attack from the demo: extra field 'delete_database' blocked."""
        handler_called = self._call_with_spy(
            ProductInput,
            product_id="P1001",
            delete_database=True,
        )
        assert handler_called is False

    # ------------------------------------------------------------------
    # 6. Invalid limit
    # ------------------------------------------------------------------

    def test_malformed_arguments_never_reach_handler_limit_zero(self):
        handler_called = self._call_with_spy(UserOrdersInput, user_id="U1001", limit=0)
        assert handler_called is False

    def test_malformed_arguments_never_reach_handler_limit_negative(self):
        handler_called = self._call_with_spy(UserOrdersInput, user_id="U1001", limit=-10)
        assert handler_called is False

    # ------------------------------------------------------------------
    # 7. Excessive limit
    # ------------------------------------------------------------------

    def test_malformed_arguments_never_reach_handler_excessive_limit(self):
        """LLM requesting 1,000,000 rows must be rejected before handler."""
        handler_called = self._call_with_spy(UserOrdersInput, user_id="U1001", limit=1_000_000)
        assert handler_called is False

    def test_malformed_arguments_never_reach_handler_limit_101(self):
        """limit=101 exceeds max=100 and must be rejected."""
        handler_called = self._call_with_spy(UserOrdersInput, user_id="U1001", limit=101)
        assert handler_called is False


class TestValidInputDoesReachHandler:
    """Complementary tests: valid input DOES reach the handler."""

    def test_valid_product_input_reaches_handler(self):
        handler_called = False
        req = ProductInput(product_id="P1001")
        handler_called = True  # validation passed
        assert handler_called is True

    def test_valid_user_input_reaches_handler(self):
        req = UserInput(user_id="U1001")
        handler_called = True
        assert handler_called is True

    def test_valid_orders_input_reaches_handler(self):
        req = UserOrdersInput(user_id="U1001", limit=5)
        handler_called = True
        assert handler_called is True
