"""Immutable seeded call-tape generation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

from city_os.contracts.api import CallPriority, ScenarioObservation


@dataclass(frozen=True, slots=True)
class CallEvent:
    """One policy-independent emergency event and its service draw."""

    id: str
    occurred_at_second: float
    occurred_at_minute: int
    h3_cell: str
    node_id: int
    priority: CallPriority
    on_scene_seconds: float
    transport_seconds: float
    handoff_seconds: float

    @property
    def service_seconds(self) -> float:
        return self.on_scene_seconds + self.transport_seconds + self.handoff_seconds


def _records(density: Any) -> list[dict[str, Any]]:
    if hasattr(density, "to_dict"):
        return list(density.to_dict(orient="records"))
    result = []
    for item in density:
        if isinstance(item, Mapping):
            result.append(dict(item))
        elif hasattr(item, "model_dump"):
            result.append(item.model_dump())
        else:
            result.append(vars(item))
    return result


def _minute(value: object, origin: datetime | None) -> int:
    if isinstance(value, datetime):
        if origin is None:
            return 0
        return max(0, int((value - origin).total_seconds() // 60))
    if isinstance(value, (int, float, str)):
        return int(value)
    raise TypeError("bucket_start/minute must be a datetime or numeric value")


def _clock_minute(value: str) -> int:
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute


def _multiplier(
    cell: str,
    minute: int,
    scenarios: tuple[ScenarioObservation, ...],
    origin_clock: int,
) -> float:
    clock = (origin_clock + minute) % (24 * 60)
    factor = 1.0
    for scenario in scenarios:
        active = _clock_minute(scenario.starts_at) <= clock < _clock_minute(scenario.ends_at)
        if cell in scenario.affected_h3 and active:
            factor *= scenario.demand_multiplier
    return factor


def generate_call_tape(
    density: Any,
    scenarios: Iterable[ScenarioObservation],
    seed: int,
    duration_minutes: int = 360,
    *,
    node_by_h3: Mapping[str, int] | None = None,
) -> tuple[CallEvent, ...]:
    """Draw a stable inhomogeneous Poisson tape from five-minute H3 intensity.

    Input accepts H3Density objects, mappings, or a pandas DataFrame. Intensity is
    calls/hour; the latest known bucket is carried forward for sparse demo data.
    """
    if seed < 0 or duration_minutes <= 0:
        raise ValueError("seed must be non-negative and duration_minutes positive")
    rows = _records(density)
    if not rows:
        return ()
    times = [row.get("bucket_start", row.get("minute", 0)) for row in rows]
    datetimes = [value for value in times if isinstance(value, datetime)]
    origin = min(datetimes) if datetimes else None
    origin_clock = origin.hour * 60 + origin.minute if origin is not None else 0
    by_cell: dict[str, list[tuple[int, float]]] = {}
    for row, value in zip(rows, times, strict=True):
        cell = str(row.get("cell", row.get("h3_cell")))
        intensity = float(row.get("emergency_intensity_hour", row.get("intensity", 0.0)))
        by_cell.setdefault(cell, []).append((_minute(value, origin), max(0.0, intensity)))
    for values in by_cell.values():
        values.sort()
    scenario_tuple = tuple(sorted(scenarios, key=lambda item: (item.starts_at, item.id)))
    rng = np.random.default_rng(seed)
    pending: list[tuple[float, str, CallPriority, float, float, float]] = []
    for minute in range(0, duration_minutes, 5):
        for cell in sorted(by_cell):
            history = by_cell[cell]
            applicable = [intensity for bucket, intensity in history if bucket <= minute]
            intensity = applicable[-1] if applicable else history[0][1]
            factor = _multiplier(cell, minute, scenario_tuple, origin_clock)
            count = int(rng.poisson(intensity * factor / 12.0))
            for _ in range(count):
                bucket_seconds = min(300.0, (duration_minutes - minute) * 60.0)
                occurred = minute * 60.0 + float(rng.uniform(0.0, bucket_seconds))
                priority = CallPriority(int(rng.choice((1, 2, 3), p=(0.18, 0.47, 0.35))))
                priority_scale = {
                    CallPriority.P1: 1.15,
                    CallPriority.P2: 1.0,
                    CallPriority.P3: 0.85,
                }
                scale = priority_scale[priority]
                on_scene = float(rng.lognormal(np.log(900.0 * scale), 0.25))
                transport = float(rng.lognormal(np.log(720.0 * scale), 0.30))
                handoff = float(rng.lognormal(np.log(600.0 * scale), 0.25))
                pending.append((occurred, cell, priority, on_scene, transport, handoff))
    pending.sort(key=lambda item: (item[0], item[1], int(item[2])))
    nodes = node_by_h3 or {cell: index for index, cell in enumerate(sorted(by_cell))}
    return tuple(
        CallEvent(
            id=f"call-{index:06d}",
            occurred_at_second=occurred,
            occurred_at_minute=int(occurred // 60),
            h3_cell=cell,
            node_id=int(nodes[cell]),
            priority=priority,
            on_scene_seconds=on_scene,
            transport_seconds=transport,
            handoff_seconds=handoff,
        )
        for index, (occurred, cell, priority, on_scene, transport, handoff) in enumerate(pending, 1)
    )
