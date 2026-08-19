from __future__ import annotations

import networkx as nx
import pytest
import base64
from shapely import wkb
from shapely.geometry import LineString

from city_os.spatial.osm_graph import normalize_osm_graph


def make_graph(reverse_insertion: bool = False) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    node_rows = [(1, -46.65, -23.56), (2, -46.64, -23.56), (3, -46.63, -23.55)]
    if reverse_insertion:
        node_rows.reverse()
    for node_id, x, y in node_rows:
        graph.add_node(node_id, x=x, y=y)
    edge_rows = [
        (1, 2, "main", {"length": 1_000, "highway": "primary", "maxspeed": "50 km/h", "osmid": 10}),
        (1, 2, "bus", {"length": 1_050, "highway": "secondary", "maxspeed": "30", "osmid": 11}),
        (2, 1, "reverse", {"length": 1_000, "highway": "primary", "maxspeed": "50", "osmid": 12}),
        (2, 3, "forward", {"length": 1_500, "highway": "residential", "osmid": 13}),
    ]
    if reverse_insertion:
        edge_rows.reverse()
    for u, v, key, attrs in edge_rows:
        attrs["geometry"] = LineString([(graph.nodes[u]["x"], graph.nodes[u]["y"]), (graph.nodes[v]["x"], graph.nodes[v]["y"])])
        graph.add_edge(u, v, key=key, **attrs)
    return graph


def test_normalization_retains_reverse_and_parallel_arcs_stably() -> None:
    nodes, edges = normalize_osm_graph(make_graph())
    reordered_nodes, reordered_edges = normalize_osm_graph(make_graph(reverse_insertion=True))

    assert len(nodes) == 3
    assert len(edges) == 4
    assert len({edge.edge_id for edge in edges}) == 4
    assert [(edge.edge_id, edge.u, edge.v) for edge in edges] == [
        (edge.edge_id, edge.u, edge.v) for edge in reordered_edges
    ]
    assert [node.node_id for node in nodes] == [0, 1, 2]
    assert [(node.node_id, node.h3_cell) for node in nodes] == [
        (node.node_id, node.h3_cell) for node in reordered_nodes
    ]
    assert {(edge.u, edge.v) for edge in edges} >= {(0, 1), (1, 0), (1, 2)}
    assert all(edge.free_flow_seconds > 0 and edge.capacity_vph > 0 for edge in edges)
    assert all(wkb.loads(base64.b64decode(edge.geometry_wkb)).geom_type == "LineString" for edge in edges)


def test_speed_capacity_and_validation() -> None:
    _, edges = normalize_osm_graph(make_graph())
    primary = next(edge for edge in edges if edge.u == 0 and edge.length_m == 1_000)
    assert primary.free_flow_seconds == pytest.approx(72.0)
    assert primary.capacity_vph == 1_500

    undirected = nx.MultiGraph()
    with pytest.raises(TypeError, match="directed MultiDiGraph"):
        normalize_osm_graph(undirected)
