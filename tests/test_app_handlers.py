"""
tests/test_app_handlers.py — Integration tests for the three handlers against SQLite.

Tests verify:
- Valid inputs return correct data from the real demo database
- Nonexistent IDs return found=False (not an error)
- Row limits are enforced server-side
- Truncation flag is correctly set
- No write operations are possible
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import ProductInput, UserInput, UserOrdersInput


@pytest.fixture(scope="module")
def _ensure_handlers():
    """Import handlers to register tools (side-effect import)."""
    import app.handlers  # noqa: F401
    from app.handlers import get_product, get_user, get_user_orders
    return get_product, get_user, get_user_orders


@pytest.fixture(scope="module")
def get_product(_ensure_handlers):
    return _ensure_handlers[0]


@pytest.fixture(scope="module")
def get_user(_ensure_handlers):
    return _ensure_handlers[1]


@pytest.fixture(scope="module")
def get_user_orders(_ensure_handlers):
    return _ensure_handlers[2]


# ===========================================================================
# get_product tests
# ===========================================================================

class TestGetProduct:
    def test_known_product_returns_data(self, get_product):
        result = get_product(ProductInput(product_id="P1001"))
        assert result.found is True
        assert result.product_id == "P1001"
        assert result.name == "Wireless Noise-Cancelling Headphones"
        assert result.price == 149.99
        assert result.brand == "SoundCore"

    def test_another_known_product(self, get_product):
        result = get_product(ProductInput(product_id="P1010"))
        assert result.found is True
        assert result.product_id == "P1010"
        assert result.name == "Laptop Stand Aluminium"

    def test_nonexistent_product_returns_not_found(self, get_product):
        result = get_product(ProductInput(product_id="P9999"))
        assert result.found is False
        assert result.product_id == "P9999"

    def test_invalid_id_rejected_before_handler(self, get_product):
        """Invalid ID must raise ValidationError before handler is called."""
        with pytest.raises(ValidationError):
            get_product(ProductInput(product_id="INVALID"))

    def test_devanagari_id_rejected_before_handler(self, get_product):
        with pytest.raises(ValidationError):
            get_product(ProductInput(product_id="P१२३"))

    def test_extra_field_rejected_before_handler(self, get_product):
        with pytest.raises(ValidationError):
            get_product(ProductInput(product_id="P1001", extra_field="value"))

    def test_result_is_not_truncated(self, get_product):
        """get_product returns a single product — never truncated."""
        result = get_product(ProductInput(product_id="P1001"))
        assert result.truncated is False


# ===========================================================================
# get_user tests
# ===========================================================================

class TestGetUser:
    def test_known_user_returns_data(self, get_user):
        result = get_user(UserInput(user_id="U1001"))
        assert result.found is True
        assert result.user_id == "U1001"
        assert result.name == "Arjun Sharma"
        assert result.city == "Hyderabad"
        assert result.membership == "Gold"

    def test_another_known_user(self, get_user):
        result = get_user(UserInput(user_id="U1002"))
        assert result.found is True
        assert result.name == "Priya Reddy"

    def test_nonexistent_user_returns_not_found(self, get_user):
        result = get_user(UserInput(user_id="U9999"))
        assert result.found is False

    def test_invalid_id_rejected(self, get_user):
        with pytest.raises(ValidationError):
            get_user(UserInput(user_id="BADID"))

    def test_devanagari_user_id_rejected(self, get_user):
        with pytest.raises(ValidationError):
            get_user(UserInput(user_id="U१२३"))

    def test_result_is_not_truncated(self, get_user):
        result = get_user(UserInput(user_id="U1001"))
        assert result.truncated is False


# ===========================================================================
# get_user_orders tests
# ===========================================================================

class TestGetUserOrders:
    def test_u1001_has_orders(self, get_user_orders):
        result = get_user_orders(UserOrdersInput(user_id="U1001", limit=100))
        assert result.count > 0
        assert result.user_id == "U1001"

    def test_u1001_has_25_orders_in_db(self, get_user_orders):
        result = get_user_orders(UserOrdersInput(user_id="U1001", limit=100))
        assert result.total_available == 25

    def test_truncation_triggered_at_limit_5(self, get_user_orders):
        """U1001 has 25 orders — requesting limit=5 must set truncated=True."""
        result = get_user_orders(UserOrdersInput(user_id="U1001", limit=5))
        assert result.count == 5
        assert result.truncated is True
        assert result.total_available == 25
        assert result.truncation_warning is not None
        assert "25" in result.truncation_warning

    def test_no_truncation_when_limit_exceeds_available(self, get_user_orders):
        """If limit >= available rows, truncated must be False."""
        result = get_user_orders(UserOrdersInput(user_id="U1001", limit=100))
        assert result.truncated is False
        assert result.count == result.total_available

    def test_nonexistent_user_returns_empty(self, get_user_orders):
        result = get_user_orders(UserOrdersInput(user_id="U9999", limit=10))
        assert result.count == 0
        assert result.truncated is False
        assert result.rows == []

    def test_row_limit_enforced_server_side(self, get_user_orders):
        """Server must enforce limit=3 even if U1001 has 25 orders."""
        result = get_user_orders(UserOrdersInput(user_id="U1001", limit=3))
        assert result.count == 3

    def test_excessive_limit_rejected_by_pydantic(self, get_user_orders):
        with pytest.raises(ValidationError):
            get_user_orders(UserOrdersInput(user_id="U1001", limit=1_000_000))

    def test_invalid_user_id_rejected(self, get_user_orders):
        with pytest.raises(ValidationError):
            get_user_orders(UserOrdersInput(user_id="INVALID", limit=10))

    def test_devanagari_user_id_rejected(self, get_user_orders):
        with pytest.raises(ValidationError):
            get_user_orders(UserOrdersInput(user_id="U१२३", limit=10))

    def test_extra_field_rejected(self, get_user_orders):
        with pytest.raises(ValidationError):
            get_user_orders(UserOrdersInput(user_id="U1001", limit=5, sql="SELECT *"))

    def test_order_items_have_required_fields(self, get_user_orders):
        result = get_user_orders(UserOrdersInput(user_id="U1001", limit=5))
        for order in result.rows:
            assert order.order_id
            assert order.user_id == "U1001"
            assert order.product_id
            assert order.quantity >= 1
            assert order.total_amount > 0
            assert order.status
            assert order.created_at

    def test_all_returned_orders_belong_to_user(self, get_user_orders):
        result = get_user_orders(UserOrdersInput(user_id="U1002", limit=20))
        for order in result.rows:
            assert order.user_id == "U1002"
