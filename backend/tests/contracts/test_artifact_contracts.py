"""Validation contracts for the spatial and sensor artifact rows."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from city_os.contracts.artifacts import (
    ArtifactChecksum,
    ArtifactEntry,
    ArtifactManifest,
    CameraObservation,
    EdgeState,
    H3Density,
    RoadEdge,
    RoadNode,
)

H3_R8 = "8828308281fffff"
BUCKET_START = datetime(2026, 8, 19, 12, 5, tzinfo=UTC)


def node_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "node_id": 7,
        "x": -46.6333,
        "y": -23.5505,
        "h3_cell": H3_R8,
    }
    payload.update(changes)
    return payload


def edge_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "edge_id": 11,
        "u": 7,
        "v": 8,
        "length_m": 42.5,
        "free_flow_seconds": 5.0,
        "capacity_vph": 900.0,
        "geometry_wkb": "AAE=",
    }
    payload.update(changes)
    return payload


def camera_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "camera_id": "cam-1",
        "edge_id": 11,
        "bucket_start": BUCKET_START,
        "object_class": "bus",
        "direction": "northbound",
        "count": 4,
        "confidence": 0.8,
    }
    payload.update(changes)
    return payload


def edge_state_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "edge_id": 11,
        "bucket_start": BUCKET_START,
        "flow_vph": 120.0,
        "speed_kph": 22.0,
        "travel_seconds": 8.0,
        "occupancy_people": 10.0,
        "confidence": 0.7,
    }
    payload.update(changes)
    return payload


def density_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "cell": H3_R8,
        "bucket_start": BUCKET_START,
        "density_people_km2": 3400.0,
        "emergency_intensity_hour": 1.5,
        "confidence": 0.6,
    }
    payload.update(changes)
    return payload


def manifest_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "artifacts": (
            {
                "name": "roads",
                "path": "roads/nodes.parquet",
                "media_type": "application/vnd.apache.parquet",
                "checksum": {"algorithm": "sha256", "value": "a" * 64},
            },
        ),
    }
    payload.update(changes)
    return payload


def test_artifact_rows_accept_valid_frozen_contract_values() -> None:
    """Removing a frozen field or its valid domain must reject this fixture."""
    assert RoadNode.model_validate(node_payload()).h3_cell == H3_R8
    assert RoadEdge.model_validate(edge_payload()).geometry_wkb == "AAE="
    assert CameraObservation.model_validate(camera_payload()).bucket_start == BUCKET_START
    assert EdgeState.model_validate(edge_state_payload()).flow_vph == 120.0
    assert H3Density.model_validate(density_payload()).cell == H3_R8


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (RoadNode, node_payload(unexpected=True)),
        (RoadEdge, edge_payload(unexpected=True)),
        (CameraObservation, camera_payload(unexpected=True)),
        (EdgeState, edge_state_payload(unexpected=True)),
        (H3Density, density_payload(unexpected=True)),
    ],
)
def test_artifact_rows_forbid_unknown_fields(
    model: type[object], payload: dict[str, object]
) -> None:
    """Dropping extra-forbid would silently permit producer schema drift."""
    with pytest.raises(ValidationError):
        model.model_validate(payload)  # type: ignore[attr-defined]


@pytest.mark.parametrize("invalid_h3", ["8828308281ffffe", "8928308280fffff", "not-an-h3-cell"])
def test_spatial_rows_require_real_h3_resolution_eight_cells(invalid_h3: str) -> None:
    """Replacing H3 validation with a hexadecimal regex accepts wrong-world cells."""
    with pytest.raises(ValidationError):
        RoadNode.model_validate(node_payload(h3_cell=invalid_h3))
    with pytest.raises(ValidationError):
        H3Density.model_validate(density_payload(cell=invalid_h3))


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (RoadNode, node_payload(node_id=-1)),
        (RoadEdge, edge_payload(edge_id=-1)),
        (RoadEdge, edge_payload(u=-1)),
        (RoadEdge, edge_payload(v=-1)),
        (CameraObservation, camera_payload(edge_id=-1)),
        (CameraObservation, camera_payload(count=-1)),
        (EdgeState, edge_state_payload(edge_id=-1)),
    ],
)
def test_identifier_and_count_bounds_reject_negative_integers(
    model: type[object], payload: dict[str, object]
) -> None:
    """Removing integer lower bounds accepts invalid graph or observation IDs."""
    with pytest.raises(ValidationError):
        model.model_validate(payload)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (RoadNode, node_payload(x=180.00001)),
        (RoadNode, node_payload(y=-90.00001)),
        (RoadEdge, edge_payload(length_m=0)),
        (RoadEdge, edge_payload(free_flow_seconds=0)),
        (RoadEdge, edge_payload(capacity_vph=-0.1)),
        (CameraObservation, camera_payload(confidence=1.01)),
        (EdgeState, edge_state_payload(flow_vph=-0.1)),
        (EdgeState, edge_state_payload(confidence=-0.1)),
        (H3Density, density_payload(density_people_km2=-0.1)),
        (H3Density, density_payload(confidence=1.01)),
    ],
)
def test_measurement_audit_bounds_are_enforced(
    model: type[object], payload: dict[str, object]
) -> None:
    """Removing measurement bounds permits physically impossible artifact values."""
    with pytest.raises(ValidationError):
        model.model_validate(payload)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (RoadNode, node_payload(x=float("nan"))),
        (RoadEdge, edge_payload(length_m=float("inf"))),
        (CameraObservation, camera_payload(confidence=float("nan"))),
        (EdgeState, edge_state_payload(speed_kph=float("inf"))),
        (H3Density, density_payload(emergency_intensity_hour=float("nan"))),
    ],
)
def test_numeric_values_must_be_finite(model: type[object], payload: dict[str, object]) -> None:
    """Removing finite-number validation admits values that cannot be serialized safely."""
    with pytest.raises(ValidationError):
        model.model_validate(payload)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (CameraObservation, camera_payload(bucket_start=datetime(2026, 8, 19, 12, 5))),
        (
            EdgeState,
            edge_state_payload(bucket_start=datetime(2026, 8, 19, 12, 6, tzinfo=UTC)),
        ),
        (
            H3Density,
            density_payload(bucket_start=datetime(2026, 8, 19, 12, 5, 1, tzinfo=UTC)),
        ),
    ],
)
def test_bucket_starts_require_aware_exact_five_minute_boundaries(
    model: type[object], payload: dict[str, object]
) -> None:
    """Removing time alignment makes spatial time-series joins nondeterministic."""
    with pytest.raises(ValidationError):
        model.model_validate(payload)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("field", "value"),
    [("camera_id", " "), ("object_class", ""), ("direction", "\t")],
)
def test_camera_strings_must_not_be_empty(field: str, value: str) -> None:
    """Removing nonempty camera text validation loses observable data semantics."""
    with pytest.raises(ValidationError):
        CameraObservation.model_validate(camera_payload(**{field: value}))


@pytest.mark.parametrize("geometry_wkb", ["", "not base64!", "AA=!"])
def test_edge_geometry_requires_nonempty_decodable_base64(geometry_wkb: str) -> None:
    """Removing base64 decoding lets malformed WKB reach spatial consumers."""
    with pytest.raises(ValidationError):
        RoadEdge.model_validate(edge_payload(geometry_wkb=geometry_wkb))


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/roads.parquet",
        "roads\\nodes.parquet",
        "./roads.parquet",
        "roads/../nodes.parquet",
        "roads//nodes.parquet",
    ],
)
def test_manifest_paths_are_safe_relative_posix_paths(path: str) -> None:
    """Relaxing path validation permits escape from the manifest directory."""
    with pytest.raises(ValidationError):
        ArtifactEntry.model_validate(
            manifest_payload()["artifacts"][0] | {"path": path}  # type: ignore[index,operator]
        )


@pytest.mark.parametrize(
    "checksum",
    [
        {"algorithm": "md5", "value": "a" * 64},
        {"algorithm": "sha256", "value": "A" * 64},
        {"algorithm": "sha256", "value": "a" * 63},
    ],
)
def test_checksums_require_lowercase_sha256(checksum: dict[str, str]) -> None:
    """Weakening the checksum contract makes immutable artifacts unverifiable."""
    with pytest.raises(ValidationError):
        ArtifactChecksum.model_validate(checksum)


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": "1.1"},
        {"artifacts": ()},
        {
            "artifacts": (
                manifest_payload()["artifacts"][0],
                manifest_payload()["artifacts"][0] | {"name": "other"},  # type: ignore[index,operator]
            )
        },
        {
            "artifacts": (
                manifest_payload()["artifacts"][0],
                manifest_payload()["artifacts"][0] | {"path": "other.parquet"},  # type: ignore[index,operator]
            )
        },
    ],
)
def test_manifest_requires_current_version_nonempty_unique_entries(
    changes: dict[str, object]
) -> None:
    """Removing manifest invariants permits ambiguous or unsupported artifact bundles."""
    with pytest.raises(ValidationError):
        ArtifactManifest.model_validate(manifest_payload(**changes))


def test_manifest_accepts_a_valid_unique_bundle() -> None:
    """A complete frozen manifest fixture remains loadable by the future loader."""
    manifest = ArtifactManifest.model_validate(manifest_payload())
    assert manifest.schema_version == "1.0"
    assert manifest.artifacts[0].path == "roads/nodes.parquet"
