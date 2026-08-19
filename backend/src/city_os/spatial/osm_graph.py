"""Normalize an OSMnx directed multigraph into stable contract records."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


try:  # Developer B owns these contracts; retain an import-only compatibility seam.
    from city_os.contracts.artifacts import RoadEdge, RoadNode
except ImportError:  # pragma: no cover - used only before the contract package lands.
    @dataclass(frozen=True, slots=True)
    class RoadNode:
        node_id: str
        x: float
        y: float
        h3_cell: str

    @dataclass(frozen=True, slots=True)
    class RoadEdge:
        edge_id: str
        u: str
        v: str
        length_m: float
        free_flow_seconds: float
        capacity_vph: float
        geometry_wkb: bytes


# Conservative urban defaults used only when OSM maxspeed is absent/unparseable.
_SPEED_KPH = {
    "motorway": 80.0,
    "motorway_link": 50.0,
    "trunk": 60.0,
    "trunk_link": 45.0,
    "primary": 50.0,
    "primary_link": 40.0,
    "secondary": 40.0,
    "secondary_link": 35.0,
    "tertiary": 35.0,
    "tertiary_link": 30.0,
    "residential": 30.0,
    "living_street": 20.0,
    "service": 20.0,
    "unclassified": 30.0,
}
_CAPACITY_VPH = {
    "motorway": 2_000.0,
    "trunk": 1_800.0,
    "primary": 1_500.0,
    "secondary": 1_200.0,
    "tertiary": 900.0,
    "residential": 600.0,
    "living_street": 300.0,
    "service": 300.0,
    "unclassified": 600.0,
}


def _first(value: Any, default: Any = None) -> Any:
    if isinstance(value, (list, tuple, set)):
        return next(iter(value), default)
    return default if value is None else value


def _road_class(attrs: Mapping[str, Any]) -> str:
    return str(_first(attrs.get("highway"), "unclassified")).lower()


def _speed_kph(attrs: Mapping[str, Any]) -> float:
    value = _first(attrs.get("maxspeed"))
    if isinstance(value, (int, float)) and math.isfinite(float(value)) and float(value) > 0:
        return float(value)
    if value:
        match = re.search(r"\d+(?:\.\d+)?", str(value))
        if match:
            speed = float(match.group())
            if "mph" in str(value).lower():
                speed *= 1.609344
            if speed > 0:
                return speed
    return _SPEED_KPH.get(_road_class(attrs), 30.0)


def _capacity(attrs: Mapping[str, Any]) -> float:
    road_class = _road_class(attrs)
    base = _CAPACITY_VPH.get(road_class, 600.0)
    lanes_value = _first(attrs.get("lanes"), 1)
    try:
        lanes = max(1.0, float(str(lanes_value).split(";")[0]))
    except (TypeError, ValueError):
        lanes = 1.0
    return base * lanes


def _h3_cell(lat: float, lng: float, resolution: int) -> str:
    import h3

    if hasattr(h3, "latlng_to_cell"):
        return str(h3.latlng_to_cell(lat, lng, resolution))
    return str(h3.geo_to_h3(lat, lng, resolution))


def _line_wkb(u_data: Mapping[str, Any], v_data: Mapping[str, Any], attrs: Mapping[str, Any]) -> bytes:
    from shapely.geometry import LineString
    from shapely import wkb

    geometry = attrs.get("geometry")
    if geometry is None:
        geometry = LineString(
            [(float(u_data["x"]), float(u_data["y"])), (float(v_data["x"]), float(v_data["y"]))]
        )
    return bytes(wkb.dumps(geometry, hex=False, output_dimension=2, byte_order=1))


def _length_m(u_data: Mapping[str, Any], v_data: Mapping[str, Any], attrs: Mapping[str, Any]) -> float:
    value = attrs.get("length")
    if value is not None:
        try:
            length = float(value)
            if math.isfinite(length) and length > 0:
                return length
        except (TypeError, ValueError):
            pass
    # Local haversine fallback; OSMnx graphs normally carry a length attribute.
    lat1, lat2 = math.radians(float(u_data["y"])), math.radians(float(v_data["y"]))
    dlat = lat2 - lat1
    dlng = math.radians(float(v_data["x"]) - float(u_data["x"]))
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return max(0.01, 6_371_008.8 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def _record(model: type[Any], **values: Any) -> Any:
    """Construct either a dataclass or Pydantic contract without copying its schema."""
    return model(**values)


def _stable_edge_id(u: Any, v: Any, key: Any, attrs: Mapping[str, Any], geometry_wkb: bytes) -> str:
    identity = {
        "u": str(u),
        "v": str(v),
        "key": str(key),
        "osmid": sorted(map(str, attrs.get("osmid", [])))
        if isinstance(attrs.get("osmid"), Iterable) and not isinstance(attrs.get("osmid"), (str, bytes))
        else str(attrs.get("osmid", "")),
        "geometry_sha256": hashlib.sha256(geometry_wkb).hexdigest(),
    }
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]
    return f"edge-{digest}"


def normalize_osm_graph(graph: Any, resolution: int = 8) -> tuple[list[RoadNode], list[RoadEdge]]:
    """Return stable nodes/arcs from a directed ``networkx.MultiDiGraph``.

    Each ``(u, v, key)`` arc is retained, including reverse and parallel arcs. The
    output is sorted by identifiers, so graph insertion order cannot affect files.
    """
    if resolution < 0 or resolution > 15:
        raise ValueError("H3 resolution must be between 0 and 15")
    if not getattr(graph, "is_directed", lambda: False)() or not getattr(graph, "is_multigraph", lambda: False)():
        raise TypeError("graph must be a directed MultiDiGraph")

    nodes: list[RoadNode] = []
    for node_id, data in graph.nodes(data=True):
        try:
            x, y = float(data["x"]), float(data["y"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"node {node_id!r} requires numeric x/y coordinates") from exc
        nodes.append(_record(RoadNode, node_id=str(node_id), x=x, y=y, h3_cell=_h3_cell(y, x, resolution)))

    edges: list[RoadEdge] = []
    for u, v, key, attrs in graph.edges(keys=True, data=True):
        u_data, v_data = graph.nodes[u], graph.nodes[v]
        geometry_wkb = _line_wkb(u_data, v_data, attrs)
        length_m = _length_m(u_data, v_data, attrs)
        speed_kph = _speed_kph(attrs)
        edges.append(
            _record(
                RoadEdge,
                edge_id=_stable_edge_id(u, v, key, attrs, geometry_wkb),
                u=str(u),
                v=str(v),
                length_m=length_m,
                free_flow_seconds=length_m / (speed_kph * 1_000 / 3_600),
                capacity_vph=_capacity(attrs),
                geometry_wkb=geometry_wkb,
            )
        )

    nodes.sort(key=lambda row: str(row.node_id))
    edges.sort(key=lambda row: str(row.edge_id))
    if len({edge.edge_id for edge in edges}) != len(edges):
        raise ValueError("stable edge identifier collision")
    return nodes, edges
