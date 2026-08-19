import math

import networkx as nx
import pytest

from city_os.routing import ScenarioEffect, TravelTimeProvider


def diamond() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    graph.add_edge(1, 2, edge_id=12, travel_seconds_by_bucket={0: 2, 1: 20})
    graph.add_edge(2, 4, edge_id=24, travel_seconds=2)
    graph.add_edge(1, 3, edge_id=13, travel_seconds=5)
    graph.add_edge(3, 4, edge_id=34, travel_seconds=5)
    return graph


def test_directed_shortest_path_and_unreachable_handling() -> None:
    provider = TravelTimeProvider(diamond())
    assert provider.shortest_seconds(1, 4, 0) == 4
    assert provider.shortest_route(1, 4, 0).nodes == (1, 2, 4)
    assert provider.shortest_seconds(4, 1, 0) == math.inf
    assert provider.shortest_route(99, 1, 0).nodes == ()


def test_time_bucket_changes_route() -> None:
    provider = TravelTimeProvider(diamond())
    assert provider.shortest_route(1, 4, 4.9).nodes == (1, 2, 4)
    assert provider.shortest_route(1, 4, 5).nodes == (1, 3, 4)


def test_blocked_edge_reroutes_and_can_make_target_unreachable() -> None:
    effects = {
        "closure": ScenarioEffect(frozenset({12})),
        "all-closed": ScenarioEffect(frozenset({12, 13})),
    }
    provider = TravelTimeProvider(diamond(), scenario_effects=effects)
    assert provider.shortest_route(1, 4, 0, ["closure"]).nodes == (1, 3, 4)
    assert provider.shortest_seconds(1, 4, 0, ["all-closed"]) == math.inf


def test_cache_is_keyed_by_source_bucket_and_canonical_scenario_signature() -> None:
    provider = TravelTimeProvider(
        diamond(), scenario_effects={"a": ScenarioEffect(), "b": ScenarioEffect()}
    )
    provider.shortest_seconds(1, 2, 0, ["b", "a", "a"])
    provider.shortest_seconds(1, 4, 4, ["a", "b"])
    assert provider.cache_info() == (1, 1, 1)
    provider.shortest_seconds(1, 4, 5, ["a", "b"])
    provider.shortest_seconds(2, 4, 5, ["a", "b"])
    assert provider.cache_info() == (1, 3, 3)


def test_rejects_invalid_inputs_and_unknown_scenarios() -> None:
    provider = TravelTimeProvider(diamond())
    with pytest.raises(ValueError, match="minute"):
        provider.shortest_seconds(1, 4, -1)
    with pytest.raises(KeyError, match="unknown"):
        provider.shortest_seconds(1, 4, 0, ["missing"])


def test_parallel_edges_use_fastest_available_arc() -> None:
    graph = nx.MultiDiGraph()
    graph.add_edge("a", "b", edge_id="slow", travel_seconds=8)
    graph.add_edge("a", "b", edge_id="fast", travel_seconds=3)
    provider = TravelTimeProvider(
        graph, scenario_effects={"close-fast": ScenarioEffect(frozenset({"fast"}))}
    )
    assert provider.shortest_seconds("a", "b", 0) == 3
    assert provider.shortest_seconds("a", "b", 0, ["close-fast"]) == 8
