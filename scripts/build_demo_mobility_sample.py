#!/usr/bin/env python3
"""Fetch a small, deterministic ARTESP traffic-count snapshot via CKAN."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from urllib.parse import urlencode

RESOURCE_ID = "447bb970-64df-4bdd-b9fd-b131bd404e00"
API = "https://dadosabertos.artesp.sp.gov.br/api/3/action/datastore_search"
START_DATE = "2025-01-01"
END_DATE = "2025-01-07"
OUTPUT = Path(__file__).parents[1] / "data/demo/mobility/artesp_sp280_km14_2025-01-01_07.csv"
FIELDS = (
    "observed_date",
    "road",
    "km",
    "km_offset_m",
    "direction",
    "carriageway",
    "motorcycles",
    "passenger_vehicles",
    "commercial_vehicles",
    "vehicle_total",
)


def fetch() -> list[dict[str, object]]:
    params = urlencode(
        {
            "resource_id": RESOURCE_ID,
            "filters": json.dumps({"RODOVIA": "SP280", "KM": "14"}),
            "limit": 5000,
        }
    )
    # curl uses the operating system trust store consistently on the supported
    # macOS demo host, unlike some standalone Python.org installations.
    response = subprocess.run(  # noqa: S603 - fixed executable and URL
        ["curl", "--fail", "--silent", "--show-error", f"{API}?{params}"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(response.stdout)
    if not payload.get("success"):
        raise RuntimeError("ARTESP CKAN request failed")
    return payload["result"]["records"]


def normalize(records: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for record in records:
        date = str(record["DATA"])
        if not START_DATE <= date <= END_DATE:
            continue
        motorcycles = int(str(record["QTD_MOTO"]))
        passenger = int(str(record["QTD_PASSEIO"]))
        commercial = int(str(record["QTD_COMERCIAL"]))
        rows.append(
            {
                "observed_date": date,
                "road": record["RODOVIA"],
                "km": int(str(record["KM"])),
                "km_offset_m": int(str(record["COMPLEMENTO"])),
                "direction": record["SENTIDO"],
                "carriageway": "marginal" if record["MARGINAL"] == "SIM" else "mainline",
                "motorcycles": motorcycles,
                "passenger_vehicles": passenger,
                "commercial_vehicles": commercial,
                "vehicle_total": motorcycles + passenger + commercial,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            str(row["observed_date"]),
            str(row["direction"]),
            str(row["carriageway"]),
            int(row["km_offset_m"]),
        ),
    )


def main() -> None:
    rows = normalize(fetch())
    if not rows:
        raise RuntimeError("ARTESP returned no records for the pinned sample window")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} observations to {OUTPUT}")


if __name__ == "__main__":
    main()
