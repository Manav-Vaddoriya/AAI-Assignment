"""
tools/manifest.py — Manifest generator and CLI.

The manifest is a JSON file that records every tool in ``TOOL_REGISTRY``:
its name, description, input-model JSON schema, default row limit, and the
module it lives in.

This file is both a library and a CLI entry point::

    # Generate and print the manifest
    python -m tools.manifest

    # Write to a specific file
    python -m tools.manifest --output manifest.json

CI check (via ``make manifest``)
---------------------------------
The Makefile runs this generator, writes to a temp file, and diffs against
the committed ``manifest.json``.  A non-empty diff fails the build.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Import handlers to populate TOOL_REGISTRY before generating the manifest.
import tools.handlers  # noqa: F401  — side-effect import
from tools.registry import TOOL_REGISTRY, ToolEntry


def _tool_to_dict(entry: ToolEntry) -> dict[str, Any]:
    """Serialise a single ``ToolEntry`` to a JSON-compatible dict."""
    # Use Pydantic's built-in JSON schema generation
    schema = entry.input_model.model_json_schema()
    return {
        "name": entry.name,
        "description": entry.description,
        "module": entry.module,
        "row_limit": entry.row_limit,
        "input_schema": schema,
    }


def generate_manifest() -> dict[str, Any]:
    """Return the full manifest as a Python dict.

    The manifest structure::

        {
            "schema_version": "1",
            "tools": [
                {
                    "name": "search_documents",
                    "description": "...",
                    "module": "tools.handlers",
                    "row_limit": 20,
                    "input_schema": { ... }   # Pydantic JSON schema
                },
                ...
            ]
        }
    """
    tools_list = [_tool_to_dict(entry) for entry in TOOL_REGISTRY.values()]
    # Sort by name for deterministic output — required for a stable diff
    tools_list.sort(key=lambda t: t["name"])
    return {
        "schema_version": "1",
        "tools": tools_list,
    }


def write_manifest(path: Path) -> None:
    """Write the manifest to *path* as pretty-printed JSON."""
    manifest = generate_manifest()
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tools.manifest",
        description="Generate the tool registry manifest.",
    )
    p.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        default=None,
        help="Write manifest to PATH instead of stdout.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    manifest = generate_manifest()
    text = json.dumps(manifest, indent=2) + "\n"

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Manifest written to {args.output!r} ({len(TOOL_REGISTRY)} tools).",
              file=sys.stderr)
    else:
        sys.stdout.write(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
