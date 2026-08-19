#!/usr/bin/env python3
"""Smoke-test the minimal SPTrans vehicle-position client."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from city_os.integrations.sptrans import SPTransClient, SPTransError  # noqa: E402


def main() -> int:
    try:
        with SPTransClient.from_env() as client:
            payload = client.fetch_vehicle_positions()
    except SPTransError as error:
        print(f"SPTrans check failed: {error}", file=sys.stderr)
        return 1

    lines = payload["l"]
    vehicles = sum(len(line.get("vs", [])) for line in lines)
    print(f"SPTrans OK: {len(lines)} lines and {vehicles} vehicles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
