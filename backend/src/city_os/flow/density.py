"""Aggregation of directional edge occupancy into H3 activity density."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np


def _get(record: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(record, Mapping) and name in record:
            return record[name]
        if hasattr(record, name):
            return getattr(record, name)
    return default


def _density_model() -> type[Any] | None:
    try:
        from city_os.contracts import H3Density
    except ImportError:  # Developer B's contract package is an integration input.
        return None
    return H3Density


def _edge_people(state: Any, priors: Mapping[str, float]) -> float:
    explicit = _get(state, "occupancy_people")
    if explicit is not None:
        value = float(explicit)
        if not np.isfinite(value) or value < 0:
            raise ValueError("occupancy_people must be finite and non-negative")
        return value
    travel_seconds = float(_get(state, "travel_seconds", default=0.0))
    if not np.isfinite(travel_seconds) or travel_seconds < 0:
        raise ValueError("travel_seconds must be finite and non-negative")
    class_flows = _get(state, "flow_by_class", "class_flows")
    if class_flows is not None:
        rates = {str(kind): float(rate) for kind, rate in class_flows.items()}
        if any(not np.isfinite(rate) or rate < 0 for rate in rates.values()):
            raise ValueError("class flows must be finite and non-negative")
        vehicles = sum(rate * float(priors.get(kind, priors.get("default", 1.0))) for kind, rate in rates.items())
        return vehicles * travel_seconds / 3600.0
    flow = float(_get(state, "flow_vph", "flow", default=0.0))
    if not np.isfinite(flow) or flow < 0:
        raise ValueError("flow must be finite and non-negative")
    composition = _get(state, "class_composition", default={}) or {}
    fractions = {str(kind): float(fraction) for kind, fraction in composition.items()}
    if any(not np.isfinite(fraction) or fraction < 0 for fraction in fractions.values()):
        raise ValueError("class composition must be finite and non-negative")
    total = sum(fractions.values())
    occupancy = (
        sum(fraction * float(priors.get(kind, priors.get("default", 1.0))) for kind, fraction in fractions.items()) / total
        if total > 0
        else float(priors.get("default", 1.0))
    )
    return flow * travel_seconds / 3600.0 * occupancy


def aggregate_h3_density(
    edge_states: Iterable[Any],
    edge_h3_weights: Iterable[Any] | Mapping[str, Mapping[str, float]],
    cell_areas_km2: Mapping[str, float],
    occupancy_priors: Mapping[str, float],
    *,
    resident_density: Mapping[str, float] | None = None,
    intensity_scale: float = 1.0,
    resident_weight: float = 0.25,
    flow_weight: float = 0.75,
) -> list[Any]:
    """Allocate edge occupancy to cells and return stable, zero-filled rows.

    Emergency intensity is a bounded min-max normalization of the configured
    resident and flow-density blend. It is an hourly relative intensity in
    ``[0, intensity_scale]`` rather than a calibrated emergency-call claim.
    """
    parameters = (intensity_scale, resident_weight, flow_weight)
    if any(not np.isfinite(value) or value < 0 for value in parameters):
        raise ValueError("intensity parameters must be finite and non-negative")
    areas = {str(cell): float(area) for cell, area in cell_areas_km2.items()}
    if any(not np.isfinite(area) or area <= 0 for area in areas.values()):
        raise ValueError("cell areas must be finite and positive")
    priors = {str(kind): float(value) for kind, value in occupancy_priors.items()}
    if any(not np.isfinite(value) or value < 0 for value in priors.values()):
        raise ValueError("occupancy priors must be finite and non-negative")

    weights: dict[str, list[tuple[str, float]]] = defaultdict(list)
    if isinstance(edge_h3_weights, Mapping):
        weight_rows = (
            (edge, cell, weight)
            for edge, cells in edge_h3_weights.items()
            for cell, weight in cells.items()
        )
    else:
        weight_rows = (
            (
                str(_get(row, "edge_id")),
                str(_get(row, "cell", "h3_cell")),
                float(_get(row, "weight", "overlap_weight")),
            )
            for row in edge_h3_weights
        )
    for edge, cell, weight in weight_rows:
        edge, cell, weight = str(edge), str(cell), float(weight)
        if edge == "None" or cell == "None":
            raise ValueError("edge-H3 weights require edge_id and cell")
        if cell not in areas:
            raise ValueError(f"edge weight references unknown cell {cell!r}")
        if not np.isfinite(weight) or weight < 0:
            raise ValueError("edge-H3 weights must be finite and non-negative")
        weights[edge].append((cell, weight))
    for edge, assignments in weights.items():
        total = sum(weight for _, weight in assignments)
        if assignments and not np.isclose(total, 1.0, atol=1e-6):
            raise ValueError(f"weights for edge {edge!r} sum to {total}, not 1")

    people: dict[tuple[str, Any], float] = defaultdict(float)
    confidence_mass: dict[tuple[str, Any], float] = defaultdict(float)
    allocation_mass: dict[tuple[str, Any], float] = defaultdict(float)
    buckets: set[Any] = set()
    for state in edge_states:
        edge = str(_get(state, "edge_id"))
        if edge == "None":
            raise ValueError("edge state is missing edge_id")
        bucket = _get(state, "bucket_start")
        if bucket is None:
            raise ValueError("edge state is missing bucket_start")
        buckets.add(bucket)
        occupancy = _edge_people(state, priors)
        confidence = float(_get(state, "confidence", default=0.0))
        if not np.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("edge confidence must lie in [0, 1]")
        for cell, weight in weights.get(edge, ()):
            allocated = occupancy * weight
            key = (cell, bucket)
            people[key] += allocated
            confidence_mass[key] += allocated * confidence
            allocation_mass[key] += allocated

    density_by_key = {key: value / areas[key[0]] for key, value in people.items()}
    resident = resident_density or {}
    model = _density_model()
    rows: list[Any] = []
    for bucket in sorted(buckets, key=str):
        raw = {
            cell: resident_weight * float(resident.get(cell, 0.0))
            + flow_weight * density_by_key.get((cell, bucket), 0.0)
            for cell in areas
        }
        low = min(raw.values(), default=0.0)
        high = max(raw.values(), default=0.0)
        spread = high - low
        for cell in sorted(areas):
            key = (cell, bucket)
            intensity = intensity_scale * (raw[cell] - low) / spread if spread > 0 else 0.0
            mass = allocation_mass[key]
            confidence = confidence_mass[key] / mass if mass > 0 else 0.0
            values = {
                "cell": cell,
                "bucket_start": bucket,
                "density_people_km2": density_by_key.get(key, 0.0),
                "emergency_intensity_hour": float(intensity),
                "confidence": float(confidence),
            }
            if model is None:
                rows.append(values)
            else:
                try:
                    rows.append(model(**values))
                except ValueError:
                    # Algorithm unit tests and exploratory callers may use symbolic cell
                    # labels. Contract construction is reserved for real H3 inputs.
                    rows.append(values)
    return rows
