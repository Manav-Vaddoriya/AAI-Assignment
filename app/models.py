"""
app/models.py — Dataclass row types for database result rows.

These are plain Python dataclasses — NOT Pydantic models.  They represent
the raw relational data as returned from SQLite before it is re-packaged into
the typed Pydantic output schemas in app/schemas.py.

Keeping them separate from the Pydantic schemas means the database layer
is not coupled to the API contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProductRow:
    """A row from the ``products`` table."""

    product_id: str
    name: str
    category: str
    price: float
    stock: int
    brand: str


@dataclass(frozen=True)
class UserRow:
    """A row from the ``users`` table."""

    user_id: str
    name: str
    city: str
    membership: str


@dataclass(frozen=True)
class OrderRow:
    """A row from the ``orders`` table."""

    order_id: str
    user_id: str
    product_id: str
    quantity: int
    total_amount: float
    status: str
    created_at: str
