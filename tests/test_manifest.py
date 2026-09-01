"""
tests/test_manifest.py — Tests for the manifest generator.

Covers
------
* All three registered tools appear in the manifest.
* Each tool entry has the required keys.
* The generated manifest matches the committed manifest.json (the CI check).
"""

import json
from pathlib import Path

import pytest

from tools.manifest import generate_manifest
from tools.registry import TOOL_REGISTRY


COMMITTED_MANIFEST = Path(__file__).parent.parent / "manifest.json"

EXPECTED_TOOLS = {"search_documents", "lookup_document", "list_documents"}


class TestGenerateManifest:
    def test_manifest_has_schema_version(self):
        manifest = generate_manifest()
        assert manifest["schema_version"] == "1"

    def test_all_three_tools_present(self):
        manifest = generate_manifest()
        names = {t["name"] for t in manifest["tools"]}
        assert EXPECTED_TOOLS.issubset(names), (
            f"Missing tools in manifest: {EXPECTED_TOOLS - names}"
        )

    def test_each_tool_has_required_keys(self):
        manifest = generate_manifest()
        required = {"name", "description", "module", "row_limit", "input_schema"}
        for tool in manifest["tools"]:
            missing = required - tool.keys()
            assert not missing, f"Tool {tool['name']!r} missing keys: {missing}"

    def test_tool_description_is_non_empty(self):
        manifest = generate_manifest()
        for tool in manifest["tools"]:
            assert tool["description"].strip(), (
                f"Tool {tool['name']!r} has an empty description in the manifest."
            )

    def test_row_limit_is_positive_integer(self):
        manifest = generate_manifest()
        for tool in manifest["tools"]:
            assert isinstance(tool["row_limit"], int)
            assert tool["row_limit"] > 0

    def test_input_schema_is_dict(self):
        manifest = generate_manifest()
        for tool in manifest["tools"]:
            assert isinstance(tool["input_schema"], dict)
            # Pydantic JSON schema always has a 'type' or '$defs' key
            assert tool["input_schema"]  # non-empty

    def test_tools_sorted_alphabetically(self):
        """Deterministic ordering is required for a stable diff."""
        manifest = generate_manifest()
        names = [t["name"] for t in manifest["tools"]]
        assert names == sorted(names), "Tools in manifest are not sorted alphabetically."

    def test_row_limit_matches_model_default(self):
        """Row limits in manifest must match what the model declares."""
        manifest = generate_manifest()
        for tool in manifest["tools"]:
            entry = TOOL_REGISTRY[tool["name"]]
            assert tool["row_limit"] == entry.row_limit


class TestCommittedManifest:
    def test_committed_manifest_exists(self):
        assert COMMITTED_MANIFEST.exists(), (
            f"Committed manifest not found at {COMMITTED_MANIFEST}.  "
            "Run `make manifest` to generate it."
        )

    def test_committed_manifest_matches_generated(self):
        """
        This is the CI check: the committed manifest.json must exactly match
        what the current registry generates.  If this test fails, run
        `make manifest` to regenerate.
        """
        with COMMITTED_MANIFEST.open(encoding="utf-8") as f:
            committed = json.load(f)

        generated = generate_manifest()

        assert committed == generated, (
            "Committed manifest.json is out of sync with the tool registry.  "
            "Run `make manifest` to regenerate and commit the updated file."
        )
