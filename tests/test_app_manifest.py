"""
tests/test_app_manifest.py — Manifest generation and drift detection tests.

Covers:
- Manifest structure (version, tools list)
- Tool entries have all required keys
- Deterministic output (same JSON on repeated calls)
- Committed manifests/tools.json matches live registry
- Drift detection raises ManifestMismatchError
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app.handlers  # noqa: F401 — populate registry

from app.manifest import (
    check_manifest,
    generate_manifest,
    manifest_to_json,
    write_manifest,
)
from app.errors import ManifestMismatchError


COMMITTED_MANIFEST = Path(__file__).parent.parent / "manifests" / "tools.json"


class TestGenerateManifest:
    """Tests for generate_manifest() return value."""

    def test_manifest_has_version(self):
        m = generate_manifest()
        assert "version" in m
        assert m["version"] == "1.0"

    def test_manifest_has_tools_list(self):
        m = generate_manifest()
        assert "tools" in m
        assert isinstance(m["tools"], list)

    def test_manifest_has_three_tools(self):
        m = generate_manifest()
        prod_tools = [t for t in m["tools"] if not t["name"].startswith("_test")]
        assert len(prod_tools) == 3

    def test_all_three_tool_names_present(self):
        m = generate_manifest()
        names = {t["name"] for t in m["tools"]}
        assert "get_product" in names
        assert "get_user" in names
        assert "get_user_orders" in names

    def test_each_tool_has_required_keys(self):
        m = generate_manifest()
        for tool in m["tools"]:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert "row_limit" in tool
            assert "read_only" in tool

    def test_all_tools_marked_read_only(self):
        m = generate_manifest()
        for tool in m["tools"]:
            if tool["name"].startswith("_test"):
                continue
            assert tool["read_only"] is True

    def test_tools_sorted_alphabetically(self):
        m = generate_manifest()
        prod_names = [t["name"] for t in m["tools"] if not t["name"].startswith("_test")]
        assert prod_names == sorted(prod_names)

    def test_row_limit_is_positive_integer(self):
        m = generate_manifest()
        for tool in m["tools"]:
            assert isinstance(tool["row_limit"], int)
            assert tool["row_limit"] >= 1

    def test_input_schema_has_additional_properties_false(self):
        """extra='forbid' must appear as additionalProperties:false in JSON schema."""
        m = generate_manifest()
        for tool in m["tools"]:
            if tool["name"].startswith("_test"):
                continue
            schema = tool["input_schema"]
            assert schema.get("additionalProperties") is False, (
                f"Tool '{tool['name']}' schema missing additionalProperties:false"
            )

    def test_product_id_pattern_uses_ascii_digits(self):
        """Pattern must use [0-9] not \\d."""
        m = generate_manifest()
        product_tool = next(t for t in m["tools"] if t["name"] == "get_product")
        schema = product_tool["input_schema"]
        product_id_prop = schema["properties"]["product_id"]
        assert "[0-9]" in product_id_prop["pattern"]
        assert "\\d" not in product_id_prop["pattern"]

    def test_user_id_pattern_uses_ascii_digits(self):
        m = generate_manifest()
        user_tool = next(t for t in m["tools"] if t["name"] == "get_user")
        schema = user_tool["input_schema"]
        user_id_prop = schema["properties"]["user_id"]
        assert "[0-9]" in user_id_prop["pattern"]
        assert "\\d" not in user_id_prop["pattern"]


class TestManifestDeterminism:
    """Manifest output must be identical on repeated calls."""

    def test_output_is_deterministic(self):
        json1 = manifest_to_json(generate_manifest())
        json2 = manifest_to_json(generate_manifest())
        assert json1 == json2

    def test_json_is_valid(self):
        text = manifest_to_json(generate_manifest())
        parsed = json.loads(text)
        assert isinstance(parsed, dict)

    def test_json_ends_with_newline(self):
        text = manifest_to_json(generate_manifest())
        assert text.endswith("\n")


class TestCommittedManifest:
    """Drift detection tests."""

    def test_committed_manifest_exists(self):
        assert COMMITTED_MANIFEST.exists(), (
            f"Committed manifest not found at {COMMITTED_MANIFEST}. "
            "Run: python scripts/generate_manifest.py --output manifests/tools.json"
        )

    def test_committed_manifest_matches_registry(self):
        """The committed manifests/tools.json must match the live registry."""
        check_manifest(COMMITTED_MANIFEST)  # raises ManifestMismatchError if drift

    def test_committed_manifest_is_valid_json(self):
        text = COMMITTED_MANIFEST.read_text(encoding="utf-8")
        parsed = json.loads(text)
        assert "tools" in parsed

    def test_drift_detection_raises_on_mismatch(self, tmp_path):
        """Modifying the committed manifest should trigger ManifestMismatchError."""
        fake_manifest = tmp_path / "tools.json"
        fake_manifest.write_text(
            '{"version": "1.0", "generated_by": "app.manifest", "tools": []}\n',
            encoding="utf-8",
        )
        with pytest.raises(ManifestMismatchError, match="Manifest drift detected"):
            check_manifest(fake_manifest)

    def test_drift_detection_raises_on_missing_file(self, tmp_path):
        missing = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            check_manifest(missing)

    def test_write_manifest_creates_file(self, tmp_path):
        out = tmp_path / "manifest_out.json"
        write_manifest(out)
        assert out.exists()
        parsed = json.loads(out.read_text(encoding="utf-8"))
        assert "tools" in parsed
