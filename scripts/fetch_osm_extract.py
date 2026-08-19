#!/usr/bin/env python3
"""Explicit build-time downloader and clipper for a pinned OSM PBF extract."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import urllib.request
from datetime import date
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Pinned HTTPS URL of the upstream .osm.pbf")
    parser.add_argument("--sha256", required=True, help="Expected SHA-256 of the upstream file")
    parser.add_argument("--boundary", type=Path, required=True, help="Official municipal GeoJSON boundary")
    parser.add_argument("--output", type=Path, required=True, help="Destination clipped .osm.pbf")
    parser.add_argument("--source-date", type=date.fromisoformat, required=True, help="Upstream snapshot date (YYYY-MM-DD)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.url.startswith("https://"):
        raise SystemExit("--url must be an explicit HTTPS URL")
    if len(args.sha256) != 64 or any(char not in "0123456789abcdefABCDEF" for char in args.sha256):
        raise SystemExit("--sha256 must contain 64 hexadecimal characters")
    if not args.boundary.is_file():
        raise SystemExit(f"boundary does not exist: {args.boundary}")
    osmium = shutil.which("osmium")
    if osmium is None:
        raise SystemExit("osmium-tool is required to clip the verified extract")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="city-os-osm-") as temp_name:
        downloaded = Path(temp_name) / "upstream.osm.pbf"
        request = urllib.request.Request(args.url, headers={"User-Agent": "City-OS-artifact-builder/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response, downloaded.open("wb") as target:
            shutil.copyfileobj(response, target)
        actual = sha256(downloaded)
        if actual.lower() != args.sha256.lower():
            raise SystemExit(f"upstream checksum mismatch: expected {args.sha256.lower()}, got {actual}")
        clipped = Path(temp_name) / "sao-paulo.osm.pbf"
        subprocess.run(
            [osmium, "extract", "--polygon", str(args.boundary.resolve()), "--strategy", "complete_ways", "--output", str(clipped), str(downloaded)],
            check=True,
        )
        clipped.replace(args.output)

    metadata = {
        "attribution": "© OpenStreetMap contributors",
        "license": "Open Database License (ODbL) 1.0",
        "source_date": args.source_date.isoformat(),
        "source_sha256": args.sha256.lower(),
        "source_url": args.url,
        "clipped_sha256": sha256(args.output),
        "boundary": args.boundary.name,
        "boundary_sha256": sha256(args.boundary),
    }
    args.output.with_suffix(args.output.suffix + ".source.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
