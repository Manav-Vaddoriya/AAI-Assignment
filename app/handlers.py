"""
app/handlers.py — Three read-only tool handlers registered at import time.

Each handler
------------
* Accepts a single validated Pydantic input model (malformed args never reach here).
* Queries the SQLite database using parameterized queries only.
* Enforces a server-side row limit independent of what the LLM requested.
* Sets ``truncated=True`` and populates ``truncation_warning`` when results are trimmed.
* Is registered via ``@read_tool``, which runs five checks at import time.

Architecture
------------
::

    User → LLM → tool call → Registry → Pydantic validation → Handler → SQLite → Result

The LLM never touches the database directly.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import ORDERS_ROW_LIMIT_MAX, PRODUCT_ROW_LIMIT, USER_ROW_LIMIT
from app.database import fetch_many, fetch_one
from app.decorators import read_tool
from app.schemas import (
    OrderItem,
    ProductInput,
    ProductResult,
    UserInput,
    UserOrdersInput,
    UserOrdersResult,
    UserResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool 1 — get_product
# ---------------------------------------------------------------------------


@read_tool(
    name="get_product",
    description="Retrieve product information by product ID. "
                "Returns name, category, price, stock, and brand for a single product.",
    row_limit=PRODUCT_ROW_LIMIT,
)
def get_product(req: ProductInput) -> ProductResult:
    """Look up a product by its unique ASCII product ID (e.g. P1001).

    The product_id must match ``^P[0-9]+$``.  Pydantic validates this
    before this function is called — malformed IDs never reach here.

    Parameters
    ----------
    req:
        A validated ``ProductInput``.  ``req.product_id`` is guaranteed to
        be a correctly-formatted ASCII identifier.

    Returns
    -------
    ProductResult
        Product data if found.  ``found=False`` if the ID does not exist.
    """
    t0 = time.perf_counter()
    logger.info("tool=get_product product_id=%s", req.product_id)

    row = fetch_one(
        "SELECT product_id, name, category, price, stock, brand "
        "FROM products WHERE product_id = ?",
        (req.product_id,),
    )

    duration_ms = round((time.perf_counter() - t0) * 1000, 1)

    if row is None:
        logger.info(
            "tool=get_product product_id=%s found=False duration_ms=%s",
            req.product_id, duration_ms,
        )
        return ProductResult(
            product_id=req.product_id,
            name="",
            category="",
            price=0.0,
            stock=0,
            brand="",
            found=False,
        )

    logger.info(
        "tool=get_product product_id=%s found=True duration_ms=%s",
        req.product_id, duration_ms,
    )
    return ProductResult(
        product_id=row["product_id"],
        name=row["name"],
        category=row["category"],
        price=row["price"],
        stock=row["stock"],
        brand=row["brand"],
        found=True,
    )


# ---------------------------------------------------------------------------
# Tool 2 — get_user
# ---------------------------------------------------------------------------


@read_tool(
    name="get_user",
    description="Retrieve user information by user ID. "
                "Returns name, city, and membership tier for a single user.",
    row_limit=USER_ROW_LIMIT,
)
def get_user(req: UserInput) -> UserResult:
    """Look up a user by their unique ASCII user ID (e.g. U1001).

    The user_id must match ``^U[0-9]+$``.  Pydantic validates this
    before this function is called.

    Parameters
    ----------
    req:
        A validated ``UserInput``.

    Returns
    -------
    UserResult
        User data if found.  ``found=False`` if the ID does not exist.
    """
    t0 = time.perf_counter()
    logger.info("tool=get_user user_id=%s", req.user_id)

    row = fetch_one(
        "SELECT user_id, name, city, membership FROM users WHERE user_id = ?",
        (req.user_id,),
    )

    duration_ms = round((time.perf_counter() - t0) * 1000, 1)

    if row is None:
        logger.info(
            "tool=get_user user_id=%s found=False duration_ms=%s",
            req.user_id, duration_ms,
        )
        return UserResult(
            user_id=req.user_id,
            name="",
            city="",
            membership="",
            found=False,
        )

    logger.info(
        "tool=get_user user_id=%s found=True duration_ms=%s",
        req.user_id, duration_ms,
    )
    return UserResult(
        user_id=row["user_id"],
        name=row["name"],
        city=row["city"],
        membership=row["membership"],
        found=True,
    )


# ---------------------------------------------------------------------------
# Tool 3 — get_user_orders
# ---------------------------------------------------------------------------


@read_tool(
    name="get_user_orders",
    description="Retrieve orders for a user by user ID. "
                "Returns a paginated list of orders with truncation flag if more exist.",
    row_limit=ORDERS_ROW_LIMIT_MAX,
)
def get_user_orders(req: UserOrdersInput) -> UserOrdersResult:
    """Fetch orders for the given user, applying a hard server-side row limit.

    The ``limit`` field in ``req`` is validated by Pydantic (ge=1, le=MAX_ROWS)
    before this function is called.  The server additionally caps the result
    at ``ORDERS_ROW_LIMIT_MAX`` so that even a future bug in Pydantic cannot
    cause an unbounded query.

    Parameters
    ----------
    req:
        A validated ``UserOrdersInput`` with ``user_id`` and ``limit``.

    Returns
    -------
    UserOrdersResult
        List of orders.  ``truncated=True`` if additional orders exist beyond
        the requested limit.  ``total_available`` reflects the true count.
    """
    t0 = time.perf_counter()
    # Double-enforce the cap — never trust the LLM-supplied limit
    effective_limit = min(req.limit, ORDERS_ROW_LIMIT_MAX)
    logger.info(
        "tool=get_user_orders user_id=%s requested_limit=%s effective_limit=%s",
        req.user_id, req.limit, effective_limit,
    )

    # fetch_many fetches effective_limit+1 rows to detect truncation
    rows = fetch_many(
        "SELECT order_id, user_id, product_id, quantity, total_amount, status, created_at "
        "FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (req.user_id,),
        limit=effective_limit,
    )

    # If we got limit+1 rows, there are more — we got them via fetch_many's +1 trick
    truncated = len(rows) > effective_limit
    page = rows[:effective_limit]

    # Get the total count for the truncation_warning
    total_row = fetch_one(
        "SELECT COUNT(*) AS cnt FROM orders WHERE user_id = ?",
        (req.user_id,),
    )
    total_available: int = total_row["cnt"] if total_row else 0

    duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    logger.info(
        "tool=get_user_orders user_id=%s rows=%s truncated=%s "
        "total_available=%s duration_ms=%s",
        req.user_id, len(page), truncated, total_available, duration_ms,
    )

    order_items = [
        OrderItem(
            order_id=r["order_id"],
            user_id=r["user_id"],
            product_id=r["product_id"],
            quantity=r["quantity"],
            total_amount=r["total_amount"],
            status=r["status"],
            created_at=r["created_at"],
        )
        for r in page
    ]

    return UserOrdersResult(
        user_id=req.user_id,
        rows=order_items,
        count=len(order_items),
        total_available=total_available,
        truncated=truncated,
        truncation_warning=(
            f"Results truncated: returned {len(order_items)} of "
            f"{total_available} orders for {req.user_id}. "
            f"Increase limit (max {ORDERS_ROW_LIMIT_MAX}) to retrieve more."
        )
        if truncated
        else None,
    )
