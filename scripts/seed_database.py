"""
scripts/seed_database.py — Deterministic demo database seeder.

Creates data/demo.db with three tables and enough rows to demonstrate:
- Product lookup by ID (P1001..P1020)
- User lookup by ID (U1001..U1010)
- Order listing with truncation (U1001 has 25 orders, others have 2-5)

Run once before starting the application:
    python scripts/seed_database.py

The script is idempotent — re-running it drops and recreates the tables.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# ── Resolve paths ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "demo.db"


# ── Schema DDL ────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS products (
    product_id  TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    price       REAL NOT NULL,
    stock       INTEGER NOT NULL,
    brand       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    city        TEXT NOT NULL,
    membership  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id      TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    product_id    TEXT NOT NULL,
    quantity      INTEGER NOT NULL,
    total_amount  REAL NOT NULL,
    status        TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (user_id)    REFERENCES users(user_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
"""

# ── Deterministic seed data ───────────────────────────────────────────────────

_PRODUCTS = [
    ("P1001", "Wireless Noise-Cancelling Headphones", "Electronics",   149.99, 320, "SoundCore"),
    ("P1002", "Mechanical Keyboard TKL",              "Electronics",    89.99, 215, "KeyMaster"),
    ("P1003", "27-inch 4K Monitor",                   "Electronics",   399.99,  88, "ViewTech"),
    ("P1004", "Ergonomic Office Chair",               "Furniture",     229.99,  54, "ComfortPlus"),
    ("P1005", "Standing Desk (Electric)",              "Furniture",     499.99,  31, "DeskPro"),
    ("P1006", "USB-C Hub 7-in-1",                     "Electronics",    39.99, 670, "PortLink"),
    ("P1007", "Webcam 1080p HD",                      "Electronics",    59.99, 402, "CamVision"),
    ("P1008", "Desk Lamp LED Adjustable",              "Office",         29.99, 800, "LumiDesk"),
    ("P1009", "Wireless Mouse Ergonomic",              "Electronics",    45.99, 560, "ClickEase"),
    ("P1010", "Laptop Stand Aluminium",               "Accessories",    34.99, 430, "RiseUp"),
    ("P1011", "Noise-Cancelling Earbuds",              "Electronics",    99.99, 190, "SoundCore"),
    ("P1012", "Smart Watch Series 5",                 "Wearables",     249.99,  72, "TimeTech"),
    ("P1013", "Portable SSD 1TB",                     "Storage",       109.99, 335, "DataVault"),
    ("P1014", "Mechanical Gaming Mouse",               "Gaming",         69.99, 280, "ClickEase"),
    ("P1015", "RTX 4050 Laptop GPU",                  "Electronics",   599.99,  15, "NvidiaRef"),
    ("P1016", "16GB DDR5 RAM Kit",                    "Components",     79.99, 220, "MemPro"),
    ("P1017", "1TB NVMe SSD M.2",                    "Storage",        89.99, 310, "DataVault"),
    ("P1018", "Surge Protector 6-outlet",             "Accessories",    24.99, 550, "PowerSafe"),
    ("P1019", "Cable Management Kit",                 "Accessories",    14.99, 920, "NeatDesk"),
    ("P1020", "Desk Organiser Set",                   "Office",         19.99, 710, "NeatDesk"),
]

_USERS = [
    ("U1001", "Arjun Sharma",    "Hyderabad",  "Gold"),
    ("U1002", "Priya Reddy",     "Bangalore",  "Silver"),
    ("U1003", "Kiran Patel",     "Mumbai",     "Bronze"),
    ("U1004", "Ananya Menon",    "Chennai",    "Gold"),
    ("U1005", "Ravi Kumar",      "Delhi",      "Silver"),
    ("U1006", "Sneha Iyer",      "Pune",       "Bronze"),
    ("U1007", "Vikram Singh",    "Kolkata",    "Gold"),
    ("U1008", "Deepika Nair",    "Ahmedabad",  "Silver"),
    ("U1009", "Aditya Joshi",    "Jaipur",     "Bronze"),
    ("U1010", "Meena Pillai",    "Kochi",      "Gold"),
]

# U1001 gets 25 orders to reliably trigger truncation demo
# Others get a handful
_ORDERS: list[tuple] = []

def _build_orders() -> list[tuple]:
    rows: list[tuple] = []
    oid = 1

    # U1001 — 25 orders across various products
    statuses = ["Delivered", "Shipped", "Processing", "Cancelled", "Returned"]
    for i in range(25):
        pid = f"P{1001 + (i % 20)}"
        qty = (i % 4) + 1
        price = _PRODUCTS[i % 20][3]
        total = round(price * qty, 2)
        status = statuses[i % len(statuses)]
        date = f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"
        rows.append((f"O{oid:04d}", "U1001", pid, qty, total, status, date))
        oid += 1

    # U1002..U1010 — 2–4 orders each
    for u_idx, (uid, *_) in enumerate(_USERS[1:], start=1):
        for j in range(2 + u_idx % 3):
            pid = f"P{1001 + (u_idx * 3 + j) % 20}"
            qty = j + 1
            price = _PRODUCTS[(u_idx * 3 + j) % 20][3]
            total = round(price * qty, 2)
            status = statuses[(u_idx + j) % len(statuses)]
            date = f"2026-0{(j + 1)}-{(u_idx * 2 + j + 1):02d}"
            rows.append((f"O{oid:04d}", uid, pid, qty, total, status, date))
            oid += 1

    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

def seed(db_path: Path = DB_PATH) -> None:
    """Create and populate the demo database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        # Drop existing tables so the script is idempotent
        cur.executescript("""
            DROP TABLE IF EXISTS orders;
            DROP TABLE IF EXISTS products;
            DROP TABLE IF EXISTS users;
        """)
        cur.executescript(_DDL)

        cur.executemany(
            "INSERT INTO products VALUES (?,?,?,?,?,?)", _PRODUCTS
        )
        cur.executemany(
            "INSERT INTO users VALUES (?,?,?,?)", _USERS
        )
        orders = _build_orders()
        cur.executemany(
            "INSERT INTO orders VALUES (?,?,?,?,?,?,?)", orders
        )

        conn.commit()
        print(f"[OK] Database seeded at {db_path}")
        print(f"  {len(_PRODUCTS)} products | {len(_USERS)} users | {len(orders)} orders")
        print(f"  U1001 has {sum(1 for o in orders if o[1] == 'U1001')} orders "
              "(enough to demo truncation)")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
    sys.exit(0)
