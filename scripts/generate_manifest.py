"""
scripts/generate_manifest.py — CLI for manifest generation and drift detection.

Usage
-----
::

    # Generate/update the committed manifest
    python scripts/generate_manifest.py --output manifests/tools.json

    # Drift check (CI mode) — exits nonzero if mismatch
    python scripts/generate_manifest.py --check --output manifests/tools.json

    # Print to stdout
    python scripts/generate_manifest.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path when run as a script
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Import handlers to populate TOOL_REGISTRY (side-effect import)
import app.handlers  # noqa: F401, E402

from app.manifest import check_manifest, manifest_to_json, generate_manifest, write_manifest  # noqa: E402
from app.errors import ManifestMismatchError  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="generate_manifest.py",
        description="Generate or verify the P13 tool registry manifest.",
    )
    p.add_argument(
        "--output", "-o",
        metavar="PATH",
        default=None,
        help="Write manifest to PATH (default: stdout).",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="Compare generated manifest against committed file.  "
             "Exit nonzero if they differ (CI mode).  --output is required.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.check:
        if not args.output:
            print("ERROR: --check requires --output <PATH>", file=sys.stderr)
            return 2
        path = Path(args.output)
        try:
            check_manifest(path)
            print(f"PASS — manifest at {path} matches the live registry.", file=sys.stderr)
            return 0
        except ManifestMismatchError as exc:
            print(f"FAIL — {exc}", file=sys.stderr)
            return 1
        except FileNotFoundError as exc:
            print(f"FAIL — {exc}", file=sys.stderr)
            return 1

    # Normal mode: write or print
    from app.registry import TOOL_REGISTRY  # noqa: PLC0415
    manifest = generate_manifest()
    text = manifest_to_json(manifest)

    if args.output:
        path = Path(args.output)
        write_manifest(path)
        print(
            f"Manifest written to {path!r} ({len(TOOL_REGISTRY)} tools).",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
