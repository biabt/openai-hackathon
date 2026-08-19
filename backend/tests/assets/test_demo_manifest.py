from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def test_demo_manifest_is_deterministic_and_checksummed(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    (root / "spatial").mkdir(parents=True)
    (root / "spatial" / "boundary.geojson").write_text("{}\n", encoding="utf-8")
    command = [
        sys.executable,
        str(REPO / "scripts" / "build_demo_manifest.py"),
        "--root",
        str(root),
    ]
    subprocess.run(command, check=True)
    first = (root / "manifest.json").read_bytes()
    subprocess.run(command, check=True)
    assert (root / "manifest.json").read_bytes() == first
    manifest = json.loads(first)
    entry = manifest["artifacts"][0]
    assert entry["path"] == "spatial/boundary.geojson"
    assert entry["sha256"] == hashlib.sha256(b"{}\n").hexdigest()


def test_bundled_demo_assets_match_manifest() -> None:
    root = REPO / "data" / "demo"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["offline_runtime"] is True
    paths = {entry["path"] for entry in manifest["artifacts"]}
    assert {
        "map/sao-paulo.pmtiles",
        "mobility/artesp_sp280_km14_2025-01-01_07.csv",
        "spatial/source/sao_paulo_ibge_boundary.geojson",
        "spatial/source/sao_paulo_central_drive.graphml",
        "spatial/artifacts/nodes.parquet",
        "spatial/artifacts/edges.parquet",
        "spatial/artifacts/h3_cells.geojson",
    } <= paths
    for entry in manifest["artifacts"]:
        path = root / entry["path"]
        assert path.stat().st_size == entry["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
