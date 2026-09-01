"""
app/schemas.py — Strict Pydantic v2 input/output models for the three P13 tools.

Design rules enforced here
--------------------------
* ``extra="forbid"`` on EVERY input model — an unknown argument raises
  ``ValidationError`` BEFORE the handler is called, satisfying the security
  invariant: malformed arguments never reach the handler.
* Identifier patterns use ``[0-9]`` (strict ASCII), NOT ``\\d``.
  Python's ``re`` / Pydantic ``\\d`` matches Unicode decimal digits:
    - Devanagari: P१२३  (U+0967–U+096F) → MUST be rejected
    - Fullwidth:  P１２３ (U+FF11–U+FF19) → MUST be rejected
* Row limits are validated by Pydantic field constraints AND enforced again
  server-side in handlers — the LLM is never trusted to obey the limit.

Tools defined here
------------------
1. ``get_product``      — ProductInput  / ProductResult
2. ``get_user``         — UserInput     / UserResult
3. ``get_user_orders``  — UserOrdersInput / UserOrdersResult
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.config import ORDERS_ROW_LIMIT_DEFAULT, ORDERS_ROW_LIMIT_MAX

# ---------------------------------------------------------------------------
# Shared output base
# ---------------------------------------------------------------------------


class ToolOutput(BaseModel):
    """Base class for all tool output models."""

    model_config = ConfigDict(extra="forbid")
    truncated: bool = False
    truncation_warning: Optional[str] = None


# ===========================================================================
# Tool 1 — get_product
# ===========================================================================

_PRODUCT_ID_PATTERN = r"^P[0-9]+$"
"""
Strict ASCII product identifier pattern.

  P1001  → valid
  P१२३  → INVALID (Devanagari digits matched by \\d but rejected here)
  P１２３ → INVALID (fullwidth digits)
  Pabc   → INVALID (no alpha after P)

We use [0-9] NOT \\d to restrict to ASCII digits only.
"""


class ProductInput(BaseModel):
    """Input model for the ``get_product`` tool.

    Fields
    ------
    product_id:
        Product identifier.  Must match ``^P[0-9]+$`` — strictly ASCII.
        Examples: P1001, P1002, P9999.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_id: str = Field(
        ...,
        pattern=_PRODUCT_ID_PATTERN,
        description="Product identifier. Format: P followed by ASCII digits. Example: P1001",
        examples=["P1001", "P1005"],
        json_schema_extra={"pattern_note": "Uses [0-9] not \\d — ASCII only"},
    )


class ProductResult(ToolOutput):
    """Output model for the ``get_product`` tool."""

    product_id: str
    name: str
    category: str
    price: float
    stock: int
    brand: str
    found: bool = True


# ===========================================================================
# Tool 2 — get_user
# ===========================================================================

_USER_ID_PATTERN = r"^U[0-9]+$"
"""
Strict ASCII user identifier pattern.

  U1001  → valid
  U१२३  → INVALID
  u1001  → INVALID (lowercase u)
"""


class UserInput(BaseModel):
    """Input model for the ``get_user`` tool.

    Fields
    ------
    user_id:
        User identifier.  Must match ``^U[0-9]+$`` — strictly ASCII.
        Examples: U1001, U1002.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_id: str = Field(
        ...,
        pattern=_USER_ID_PATTERN,
        description="User identifier. Format: U followed by ASCII digits. Example: U1001",
        examples=["U1001", "U1005"],
        json_schema_extra={"pattern_note": "Uses [0-9] not \\d — ASCII only"},
    )


class UserResult(ToolOutput):
    """Output model for the ``get_user`` tool."""

    user_id: str
    name: str
    city: str
    membership: str
    found: bool = True


# ===========================================================================
# Tool 3 — get_user_orders
# ===========================================================================


class UserOrdersInput(BaseModel):
    """Input model for the ``get_user_orders`` tool.

    Fields
    ------
    user_id:
        User identifier.  Must match ``^U[0-9]+$``.
    limit:
        Maximum number of orders to return.  Capped server-side at
        ``ORDERS_ROW_LIMIT_MAX`` (default 100).  The LLM cannot override this.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_id: str = Field(
        ...,
        pattern=_USER_ID_PATTERN,
        description="User identifier. Format: U followed by ASCII digits. Example: U1001",
        examples=["U1001"],
        json_schema_extra={"pattern_note": "Uses [0-9] not \\d — ASCII only"},
    )
    limit: int = Field(
        default=ORDERS_ROW_LIMIT_DEFAULT,
        ge=1,
        le=ORDERS_ROW_LIMIT_MAX,
        description=f"Maximum orders to return (1–{ORDERS_ROW_LIMIT_MAX}). "
                    "Server enforces this even if LLM requests more.",
    )


class OrderItem(BaseModel):
    """A single order row returned by ``get_user_orders``."""

    model_config = ConfigDict(extra="forbid")

    order_id: str
    user_id: str
    product_id: str
    quantity: int
    total_amount: float
    status: str
    created_at: str


class UserOrdersResult(ToolOutput):
    """Output model for the ``get_user_orders`` tool."""

    user_id: str
    rows: list[OrderItem] = Field(default_factory=list)
    count: int = 0
    total_available: int = 0
