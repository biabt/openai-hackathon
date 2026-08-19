#!/usr/bin/env python3
"""Validate every bundled demo asset without touching the network."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "fixtures" / "flow" / "manifest.json"
REQUIRED = (
    ROOT / "backend" / "uv.lock",
    ROOT / "frontend" / "package-lock.json",
    ROOT / "frontend" / "src" / "lib" / "contracts" / "schema.json",
    ROOT / "frontend" / "src" / "lib" / "contracts" / "fixtures" / "bootstrap.json",
    ROOT / "frontend" / "src" / "lib" / "contracts" / "fixtures" / "stream.jsonl",
)


def fail(message: str) -> None:
    raise SystemExit(f"offline demo is not ready: {message}")


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing artifact manifest: {path.relative_to(ROOT)}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path.relative_to(ROOT)}: {error}")
    if not isinstance(value, dict):
        fail(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def main() -> None:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED if not path.is_file()]
    if missing:
        fail("missing bundled files: " + ", ".join(missing))

    manifest = load_manifest(MANIFEST)
    version = manifest.get("schema_version")
    if not isinstance(version, str) or not version:
        fail("data/fixtures/flow/manifest.json has no schema_version")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        fail("data/fixtures/flow/manifest.json has no artifacts")

    checked = 0
    for entry in artifacts:
        if not isinstance(entry, dict):
            fail("artifact manifest contains a non-object entry")
        relative = entry.get("path")
        expected = entry.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            fail("each artifact needs string path and sha256 fields")
        path = (MANIFEST.parent / relative).resolve()
        try:
            path.relative_to(MANIFEST.parent.resolve())
        except ValueError:
            fail(f"artifact path escapes its bundle: {relative}")
        if not path.is_file():
            fail(f"missing bundled artifact: data/fixtures/flow/{relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            fail(
                f"checksum mismatch for data/fixtures/flow/{relative}; "
                "restore the tracked artifact before running offline"
            )
        checked += 1

    print(f"offline assets valid: schema {version}, {checked} checksums verified")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
