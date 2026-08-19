from datetime import datetime, timezone

import pytest

from city_os.flow.density import aggregate_h3_density


def _value(row: object, field: str):
    return row[field] if isinstance(row, dict) else getattr(row, field)


def test_spatial_allocation_conserves_people_and_zero_fills_cells() -> None:
    bucket = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
    edge_states = [
        {
            "edge_id": "a",
            "bucket_start": bucket,
            "flow_vph": 360,
            "travel_seconds": 10,
            "class_composition": {"car": 1.0},
            "confidence": 0.8,
        },
        {
            "edge_id": "b",
            "bucket_start": bucket,
            "flow_vph": 180,
            "travel_seconds": 20,
            "class_composition": {"bus": 1.0},
            "confidence": 0.6,
        },
    ]
    weights = [
        {"edge_id": "a", "cell": "cell-a", "weight": 0.25},
        {"edge_id": "a", "cell": "cell-b", "weight": 0.75},
        {"edge_id": "b", "cell": "cell-b", "weight": 1.0},
    ]
    rows = aggregate_h3_density(
        edge_states,
        weights,
        {"cell-a": 2.0, "cell-b": 4.0, "cell-c": 1.0},
        {"car": 2.0, "bus": 20.0, "default": 1.0},
    )

    assert [_value(row, "cell") for row in rows] == ["cell-a", "cell-b", "cell-c"]
    allocated_people = sum(
        _value(row, "density_people_km2")
        * {"cell-a": 2, "cell-b": 4, "cell-c": 1}[_value(row, "cell")]
        for row in rows
    )
    # Edge occupancies are 2 people and 20 people respectively.
    assert allocated_people == pytest.approx(22.0)
    assert _value(rows[-1], "density_people_km2") == 0
    assert _value(rows[-1], "confidence") == 0


def test_intensity_is_bounded_non_negative_and_order_is_stable() -> None:
    bucket = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
    rows = aggregate_h3_density(
        [{"edge_id": "e", "bucket_start": bucket, "occupancy_people": 10, "confidence": 1}],
        {"e": {"z": 0.4, "a": 0.6}},
        {"z": 1, "a": 1},
        {"default": 1},
        resident_density={"z": 100, "a": 20},
        intensity_scale=3,
    )
    assert [_value(row, "cell") for row in rows] == ["a", "z"]
    assert all(0 <= _value(row, "emergency_intensity_hour") <= 3 for row in rows)


def test_invalid_edge_weights_are_rejected() -> None:
    with pytest.raises(ValueError, match="sum"):
        aggregate_h3_density([], {"edge": {"cell": 0.5}}, {"cell": 1}, {"default": 1})
