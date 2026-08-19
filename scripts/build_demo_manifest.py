#!/usr/bin/env python3
"""Create a deterministic checksum manifest for bundled City OS demo assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


TEXT_SUFFIXES = {".csv", ".geojson", ".graphml", ".json", ".md", ".txt"}


def normalize_text_bytes(path: Path) -> None:
    """Keep checksummed text assets byte-stable across Windows and Unix checkouts."""
    if path.suffix.casefold() not in TEXT_SUFFIXES:
        return
    payload = path.read_bytes()
    normalized = payload.replace(b"\r\n", b"\n")
    if normalized != payload:
        path.write_bytes(normalized)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path) -> dict[str, object]:
    """Describe all files below ``root`` except the generated manifest itself."""
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == root / "manifest.json":
            continue
        normalize_text_bytes(path)
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    if not entries:
        raise ValueError(f"no demo assets found under {root}")
    return {
        "schema_version": "1.0",
        "bundle": "city-os-sao-paulo-demo",
        "offline_runtime": True,
        "artifacts": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/demo"))
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(args.root)
    output = args.root / "manifest.json"
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
