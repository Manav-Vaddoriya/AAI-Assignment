"""
scripts/demo_scenarios.py — Pre-built demo scenarios for the P13 presentation.

Seven scenarios covering the full demo script.
Can be run directly or imported by the UI.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import app.handlers  # noqa: F401

from app.schemas import ProductInput, UserInput, UserOrdersInput
from pydantic import ValidationError


SCENARIOS = [
    {
        "id": 1,
        "title": "Normal tool call - product lookup",
        "description": "Retrieve product P1001 using get_product.",
        "tool": "get_product",
        "args": {"product_id": "P1001"},
        "expected": "VALID",
    },
    {
        "id": 2,
        "title": "User lookup",
        "description": "Retrieve user U1001 using get_user.",
        "tool": "get_user",
        "args": {"user_id": "U1001"},
        "expected": "VALID",
    },
    {
        "id": 3,
        "title": "Truncation - orders with low limit",
        "description": "Retrieve first 5 orders for U1001 (U1001 has 25 total).",
        "tool": "get_user_orders",
        "args": {"user_id": "U1001", "limit": 5},
        "expected": "VALID (truncated=True)",
    },
    {
        "id": 4,
        "title": "Invalid identifier - PABC",
        "description": "Try to fetch product PABC -- fails pattern ^P[0-9]+$.",
        "tool": "get_product",
        "args": {"product_id": "PABC"},
        "expected": "REJECTED",
    },
    {
        "id": 5,
        "title": "Unicode digit trap - Devanagari digits",
        "description": "Devanagari digits look like digits but must be rejected. [0-9] blocks them.",
        "tool": "get_product",
        "args": {"product_id": "P\u0967\u0968\u0969"},  # P१२३
        "expected": "REJECTED",
    },
    {
        "id": 6,
        "title": "Extra field attack - delete_database",
        "description": "Simulated attack: extra='forbid' blocks the unexpected field before handler runs.",
        "tool": "get_product",
        "args": {"product_id": "P1001", "delete_database": True},
        "expected": "REJECTED",
    },
    {
        "id": 7,
        "title": "Excessive limit - LLM requests 1000000 rows",
        "description": "Server enforces le=100 on limit field -- LLM cannot bypass this.",
        "tool": "get_user_orders",
        "args": {"user_id": "U1001", "limit": 1_000_000},
        "expected": "REJECTED",
    },
]


MODEL_MAP = {
    "get_product": ProductInput,
    "get_user": UserInput,
    "get_user_orders": UserOrdersInput,
}


def run_all_scenarios():
    """Run all demo scenarios and print results."""
    from app.registry import TOOL_REGISTRY

    print("=" * 60)
    print("P13 Demo Scenarios")
    print("=" * 60)

    all_pass = True
    for s in SCENARIOS:
        model_cls = MODEL_MAP[s["tool"]]
        handler_called = False
        try:
            validated = model_cls(**s["args"])
            handler_called = True
            entry = TOOL_REGISTRY[s["tool"]]
            result = entry.handler(validated)
            status = "VALID"
            detail = str(result)[:80]
        except ValidationError as exc:
            status = "REJECTED"
            detail = exc.errors(include_url=False)[0]["msg"]

        expected = s["expected"].split()[0]  # first word
        ok = status == expected
        all_pass = all_pass and ok

        mark = "[PASS]" if ok else "[FAIL]"
        # Use ascii() to safely represent args containing non-ASCII characters
        args_repr = repr(s["args"]).encode("ascii", errors="backslashreplace").decode("ascii")
        print(f"\n{mark} Scenario {s['id']}: {s['title']}")
        print(f"  Tool: {s['tool']} | Args: {args_repr}")
        print(f"  Expected: {s['expected']} | Got: {status}")
        print(f"  handler_called: {handler_called}")
        if detail:
            print(f"  Detail: {detail}")

    print("\n" + "=" * 60)
    print(f"Result: {'ALL PASS' if all_pass else 'SOME FAILURES'}")
    return all_pass


if __name__ == "__main__":
    ok = run_all_scenarios()
    sys.exit(0 if ok else 1)
