"""Small, deterministic, time-aware shortest-path service.

The provider deliberately accepts a NetworkX graph rather than City OS artifact
models.  This keeps routing usable by both the simulator and tiny test worlds.
Edges need either ``travel_seconds`` or ``free_flow_seconds``; time-varying
values may be supplied in ``travel_seconds_by_bucket``.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

Node = Hashable
EdgeCost = Callable[[Mapping[str, Any], int], float]


@dataclass(frozen=True, slots=True)
class ScenarioEffect:
    """Routing changes activated by a scenario ID."""

    blocked_edges: frozenset[Hashable] = frozenset()
    travel_penalty: float = 1.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.travel_penalty) or self.travel_penalty <= 0:
            raise ValueError("travel_penalty must be finite and positive")


@dataclass(frozen=True, slots=True)
class Route:
    """A route result. Unreachable pairs use ``inf`` and an empty path."""

    seconds: float
    nodes: tuple[Node, ...]

    @property
    def reachable(self) -> bool:
        return math.isfinite(self.seconds)


class TravelTimeProvider:
    """Compute directed routes with deterministic five-minute caching.

    Cache identity is ``(source, time bucket, sorted scenario signature)``.
    A cached single-source tree serves repeated destinations cheaply.
    """

    def __init__(
        self,
        graph: Any,
        *,
        scenario_effects: Mapping[str, ScenarioEffect] | None = None,
        bucket_minutes: int = 5,
        edge_cost: EdgeCost | None = None,
    ) -> None:
        if not getattr(graph, "is_directed", lambda: False)():
            raise TypeError("graph must be directed")
        if bucket_minutes <= 0:
            raise ValueError("bucket_minutes must be positive")
        self.graph = graph
        self.bucket_minutes = bucket_minutes
        self.scenario_effects = MappingProxyType(dict(scenario_effects or {}))
        self._edge_cost = edge_cost or _default_edge_cost
        self._cache: dict[
            tuple[Node, int, tuple[str, ...]], tuple[dict[Node, float], dict[Node, Node]]
        ] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    def shortest_seconds(
        self,
        source: Node,
        target: Node,
        minute: int | float,
        scenario_ids: Iterable[str] = (),
    ) -> float:
        """Return travel seconds, or ``math.inf`` if no directed route exists."""
        return self.shortest_route(source, target, minute, scenario_ids).seconds

    def shortest_route(
        self,
        source: Node,
        target: Node,
        minute: int | float,
        scenario_ids: Iterable[str] = (),
    ) -> Route:
        if source not in self.graph or target not in self.graph:
            return Route(math.inf, ())
        bucket = self._bucket(minute)
        signature = tuple(sorted(set(scenario_ids)))
        unknown = set(signature).difference(self.scenario_effects)
        if unknown:
            raise KeyError(f"unknown scenario IDs: {', '.join(sorted(unknown))}")
        key = (source, bucket, signature)
        result = self._cache.get(key)
        if result is None:
            self._cache_misses += 1
            result = self._dijkstra(source, bucket, signature)
            self._cache[key] = result
        else:
            self._cache_hits += 1
        distances, previous = result
        seconds = distances.get(target, math.inf)
        if not math.isfinite(seconds):
            return Route(math.inf, ())
        path: list[Node] = [target]
        while path[-1] != source:
            path.append(previous[path[-1]])
        path.reverse()
        return Route(seconds, tuple(path))

    def clear_cache(self) -> None:
        self._cache.clear()
        self._cache_hits = self._cache_misses = 0

    def cache_info(self) -> tuple[int, int, int]:
        """Return ``(hits, misses, cached single-source trees)``."""
        return self._cache_hits, self._cache_misses, len(self._cache)

    def _bucket(self, minute: int | float) -> int:
        value = float(minute)
        if not math.isfinite(value) or value < 0:
            raise ValueError("minute must be finite and non-negative")
        return math.floor(value / self.bucket_minutes)

    def _dijkstra(
        self, source: Node, bucket: int, signature: tuple[str, ...]
    ) -> tuple[dict[Node, float], dict[Node, Node]]:
        distances: dict[Node, float] = {source: 0.0}
        previous: dict[Node, Node] = {}
        queue: list[tuple[float, str, Node]] = [(0.0, _stable(source), source)]
        while queue:
            distance, _, node = heapq.heappop(queue)
            if distance != distances.get(node):
                continue
            for neighbor in sorted(self.graph.successors(node), key=_stable):
                cost = self._neighbor_cost(node, neighbor, bucket, signature)
                if not math.isfinite(cost):
                    continue
                candidate = distance + cost
                current = distances.get(neighbor, math.inf)
                # Stable traversal makes equal-cost predecessor selection deterministic.
                if candidate < current:
                    distances[neighbor] = candidate
                    previous[neighbor] = node
                    heapq.heappush(queue, (candidate, _stable(neighbor), neighbor))
        return distances, previous

    def _neighbor_cost(
        self, source: Node, target: Node, bucket: int, signature: tuple[str, ...]
    ) -> float:
        raw = self.graph.get_edge_data(source, target)
        edges = raw.values() if getattr(self.graph, "is_multigraph", lambda: False)() else (raw,)
        costs = [self._effective_cost(edge, bucket, signature) for edge in edges]
        return min(costs, default=math.inf)

    def _effective_cost(
        self, edge: Mapping[str, Any], bucket: int, signature: tuple[str, ...]
    ) -> float:
        edge_id = edge.get("edge_id", edge.get("id"))
        if edge.get("blocked", False):
            return math.inf
        penalty = 1.0
        blocked_scenarios = set(edge.get("blocked_scenarios", ()))
        for scenario_id in signature:
            effect = self.scenario_effects[scenario_id]
            if scenario_id in blocked_scenarios or edge_id in effect.blocked_edges:
                return math.inf
            penalty *= effect.travel_penalty
        cost = float(self._edge_cost(edge, bucket))
        if cost < 0 or math.isnan(cost):
            raise ValueError(f"edge {edge_id!r} has invalid travel time")
        return cost * penalty


def _default_edge_cost(edge: Mapping[str, Any], bucket: int) -> float:
    dynamic = edge.get("travel_seconds_by_bucket")
    if callable(dynamic):
        return float(dynamic(bucket))
    if isinstance(dynamic, Mapping):
        value = dynamic.get(bucket, dynamic.get(str(bucket)))
        if value is not None:
            return float(value)
    elif dynamic is not None:
        values = tuple(dynamic)
        if values:
            return float(values[min(bucket, len(values) - 1)])
    value = edge.get("travel_seconds", edge.get("free_flow_seconds"))
    if value is None:
        raise ValueError("edge requires travel_seconds or free_flow_seconds")
    return float(value)


def _stable(value: object) -> str:
    return f"{type(value).__name__}:{value!r}"
