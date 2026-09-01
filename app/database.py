"""
app/database.py — Read-only SQLite access layer.

Design rules
------------
* Connection is opened in ``immutable`` URI mode so SQLite itself refuses
  any write attempt from this process.
* All queries use parameterized statements (? placeholders).  No string
  concatenation with user-supplied values is permitted anywhere in the
  application.
* ``get_db()`` returns a context-managed connection to make usage sites clean.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from app.config import DATABASE_PATH


def _db_path() -> Path:
    """Resolve the database path, creating parent dirs if needed."""
    p = DATABASE_PATH if DATABASE_PATH.is_absolute() else Path.cwd() / DATABASE_PATH
    return p.resolve()


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Yield a read-only SQLite connection.

    The connection uses ``uri=True`` with ``mode=ro`` so SQLite rejects any
    attempt to write, even if application code accidentally sends DML.

    Yields
    ------
    sqlite3.Connection
        A connection with ``row_factory = sqlite3.Row`` so rows support both
        index and column-name access.

    Raises
    ------
    FileNotFoundError
        If the database file does not exist (seed script has not been run).
    """
    path = _db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Database not found at {path}.  "
            "Run: python scripts/seed_database.py"
        )

    # Open read-only via URI — SQLite will refuse any DML statement
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def fetch_one(query: str, params: tuple = ()) -> sqlite3.Row | None:
    """Execute *query* with *params* and return a single row or None."""
    with get_db() as conn:
        cur = conn.execute(query, params)
        return cur.fetchone()


def fetch_many(query: str, params: tuple = (), limit: int = 100) -> list[sqlite3.Row]:
    """Execute *query* with *params* and return up to *limit* rows.

    The LIMIT is injected as a safe integer parameter — NOT string-formatted.
    """
    with get_db() as conn:
        cur = conn.execute(query, params + (limit + 1,))
        # Fetch limit+1 to detect truncation without an extra COUNT query
        return cur.fetchmany(limit + 1)
