"""
app/manifest.py — Manifest generator for the P13 tool registry.

The manifest is a machine-readable JSON file that describes every registered
tool: name, description, input JSON schema, row limit, and read-only status.

Rules
-----
* The manifest is GENERATED from the live registry — never written manually.
* Tools are sorted by name so the output is deterministic (stable diff).
* JSON is formatted with indent=2 and sorted keys for a stable diff.
* A mismatch between the committed manifest and the generated one causes CI to fail.

CLI
---
::

    # Generate and write manifest
    python scripts/generate_manifest.py --output manifests/tools.json

    # Check for drift (exits nonzero if mismatch)
    python scripts/generate_manifest.py --check --output manifests/tools.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.errors import ManifestMismatchError
from app.registry import TOOL_REGISTRY, ToolEntry


def _entry_to_dict(entry: ToolEntry) -> dict[str, Any]:
    """Serialise a single ToolEntry to a JSON-compatible dict."""
    schema = entry.input_model.model_json_schema()
    return {
        "name": entry.name,
        "description": entry.description,
        "input_schema": schema,
        "row_limit": entry.row_limit,
        "read_only": entry.read_only,
        "module": entry.module,
    }


def generate_manifest() -> dict[str, Any]:
    """Return the full manifest as a Python dict.

    Tools are sorted by name for a stable, deterministic output.

    Returns
    -------
    dict
        ``{"version": "1.0", "tools": [...]}``
    """
    tools_list = [_entry_to_dict(e) for e in TOOL_REGISTRY.values()]
    tools_list.sort(key=lambda t: t["name"])
    return {
        "version": "1.0",
        "generated_by": "app.manifest",
        "tools": tools_list,
    }


def manifest_to_json(manifest: dict[str, Any]) -> str:
    """Return a stable, pretty-printed JSON string for the manifest."""
    return json.dumps(manifest, indent=2, sort_keys=False, ensure_ascii=True) + "\n"


def write_manifest(path: Path) -> None:
    """Write the generated manifest to *path*."""
    content = manifest_to_json(generate_manifest())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def check_manifest(committed_path: Path) -> None:
    """Compare the committed manifest against the live registry.

    Raises
    ------
    ManifestMismatchError
        If the committed file differs from what would be generated now.
    FileNotFoundError
        If the committed manifest does not exist.
    """
    if not committed_path.exists():
        raise FileNotFoundError(
            f"Committed manifest not found at {committed_path}.\n"
            "Run: python scripts/generate_manifest.py --output manifests/tools.json"
        )

    committed = committed_path.read_text(encoding="utf-8")
    generated = manifest_to_json(generate_manifest())

    if committed != generated:
        raise ManifestMismatchError(
            f"Manifest drift detected!\n"
            f"The committed manifest at {committed_path} does not match "
            "the currently registered tools.\n\n"
            "Regenerate with:\n"
            "    python scripts/generate_manifest.py --output manifests/tools.json\n"
            "    git add manifests/tools.json && git commit -m 'chore: regenerate manifest'"
        )
