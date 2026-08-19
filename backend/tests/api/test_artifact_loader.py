import hashlib
import json
from pathlib import Path

import pytest

from city_os.api.artifact_loader import ArtifactLoadError, load_world


FIXTURE = Path(__file__).parents[3] / "data" / "fixtures" / "flow" / "manifest.json"


def test_loads_integrated_fixture_world() -> None:
    world = load_world(FIXTURE)
    assert (len(world.nodes), len(world.edges)) == (4, 6)
    assert (len(world.edge_states), len(world.densities)) == (12, 4)


def test_loads_checked_manifest(tmp_path: Path) -> None:
    payload = b"versioned-local-artifact"
    (tmp_path / "world.bin").write_bytes(payload)
    manifest = {
        "schema_version": "1.0",
        "artifacts": [{
            "name": "world", "path": "world.bin", "media_type": "application/octet-stream",
            "checksum": {"algorithm": "sha256", "value": hashlib.sha256(payload).hexdigest()},
        }],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    world = load_world(path)
    assert world.artifacts == {"world.bin": payload}


def test_rejects_mutated_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "nodes.parquet"
    artifact.write_bytes(b"mutated")
    manifest = {
        "schema_version": "1.0",
        "artifacts": [{
            "name": "nodes", "path": "nodes.parquet",
            "media_type": "application/vnd.apache.parquet",
            "checksum": {"algorithm": "sha256", "value": "0" * 64},
        }],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ArtifactLoadError, match="checksum mismatch"):
        load_world(path)


def test_rejects_unsupported_schema(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text('{"schema_version":"2.0","artifacts":[]}', encoding="utf-8")
    with pytest.raises(ArtifactLoadError, match="unsupported artifact schema"):
        load_world(path)
