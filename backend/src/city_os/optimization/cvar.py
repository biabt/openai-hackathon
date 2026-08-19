"""Time-bounded deterministic tail-risk placement for the MVP simulator."""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

import numpy as np

from .reposition import Allocation, DemandPoint, FleetSnapshot, Node, normalized_demand

Travel = Callable[[Node, Node], float]


@dataclass(frozen=True, slots=True)
class OptimizationConfig:
    travel: Travel
    alpha: float = 0.90
    reposition_penalty: float = 0.0
    equity_penalty: float = 0.0
    minimum_dwell_minutes: float = 15.0
    improvement_threshold: float = 0.0
    maximum_move_distance: float = math.inf
    time_limit_seconds: float = 2.0
    max_candidates: int = 64

    def __post_init__(self) -> None:
        if not 0 <= self.alpha < 1:
            raise ValueError("alpha must be in [0, 1)")


def _key(node: Node) -> str:
    return repr(node)


def _weighted_cvar(values: list[tuple[float, float]], alpha: float) -> float:
    total = sum(weight for _, weight in values)
    if total <= 0:
        return 0.0
    tail_mass = max((1.0 - alpha) * total, np.finfo(float).eps)
    remaining = tail_mass
    loss = 0.0
    for value, weight in sorted(values, reverse=True):
        used = min(weight, remaining)
        loss += value * used
        remaining -= used
        if remaining <= 0:
            break
    return loss / tail_mass


def optimize_positions(
    snapshot: FleetSnapshot,
    forecast: Iterable[DemandPoint | tuple[Node, float]],
    candidates: Sequence[Node],
    config: OptimizationConfig,
) -> Allocation:
    """Return one target per unit, preserving unavailable and young placements.

    The search starts at current positions, greedily improves each movable slot,
    then performs deterministic single-slot swaps until convergence/time limit.
    """
    points = normalized_demand(forecast)
    units = snapshot.ambulances
    if not units:
        return Allocation(())
    started = time.monotonic()
    reachable = [
        node
        for node in sorted(set(candidates), key=_key)
        if any(math.isfinite(config.travel(node, point.node)) for point in points)
    ]
    # Useful pruning: demand-near candidates before lexical tie-breaking.
    reachable.sort(
        key=lambda node: (
            sum(point.weight * config.travel(node, point.node) for point in points), _key(node)
        )
    )
    reachable = reachable[: config.max_candidates]
    if not reachable:
        raise ValueError("no candidate can reach forecast demand")
    current = tuple(unit.node for unit in units)
    movable = tuple(
        index
        for index, unit in enumerate(units)
        if unit.available
        and not unit.dispatched
        and unit.dwell_minutes >= config.minimum_dwell_minutes
    )

    def objective(positions: tuple[Node, ...]) -> float:
        responses = [
            (min(config.travel(position, point.node) for position in positions), point.weight)
            for point in points
        ]
        if any(not math.isfinite(value) for value, _ in responses):
            return math.inf
        tail = _weighted_cvar(responses, config.alpha)
        districts: dict[str, list[float]] = {}
        for (response, _), point in zip(responses, points, strict=True):
            districts.setdefault(point.district, []).append(response)
        district_means = [sum(values) / len(values) for values in districts.values()]
        equity = max(district_means) - min(district_means) if len(district_means) > 1 else 0.0
        movement = sum(config.travel(old, new) for old, new in zip(current, positions, strict=True))
        return tail + config.reposition_penalty * movement + config.equity_penalty * equity

    best = current
    best_score = objective(best)
    improved = True
    while improved and time.monotonic() - started < config.time_limit_seconds:
        improved = False
        for index in movable:
            choices = []
            for candidate in reachable:
                move = config.travel(current[index], candidate)
                if not math.isfinite(move) or move > config.maximum_move_distance:
                    continue
                trial = best[:index] + (candidate,) + best[index + 1 :]
                choices.append((objective(trial), _key(candidate), trial))
            if not choices:
                continue
            score, _, trial = min(choices)
            if best_score - score > config.improvement_threshold:
                best, best_score, improved = trial, score, True
            if time.monotonic() - started >= config.time_limit_seconds:
                break
    moved = tuple(
        unit.ambulance_id
        for unit, target in zip(units, best, strict=True)
        if unit.node != target
    )
    return Allocation(best, best_score, moved)
