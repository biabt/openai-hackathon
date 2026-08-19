"""Small deterministic event simulator for the hackathon vertical slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np

from city_os.contracts import (
    AmbulanceSnapshot,
    AmbulanceStatus,
    CallPriority,
    CallSnapshot,
    CallStatus,
    PairedMetrics,
    SimulationFrame,
    SimulationMetrics,
    SimulationPolicy,
    SimulationRequest,
)
from city_os.optimization import DemandPoint, static_p_median

from .metrics import compute_metrics

CELLS = ("88a8100c05fffff", "88a8100c57fffff")
DEMAND_NODES = (20, 30)


@dataclass(frozen=True, slots=True)
class CallEvent:
    id: str
    minute: int
    node_id: int
    h3_cell: str
    priority: CallPriority
    service_minutes: int


@dataclass(frozen=True, slots=True)
class PairedResult:
    request: SimulationRequest
    call_tape: tuple[CallEvent, ...]
    frames: tuple[SimulationFrame, ...]
    metrics: PairedMetrics


@dataclass(slots=True)
class _Unit:
    id: str
    node_id: int
    available_at: float = 0.0


@dataclass(frozen=True, slots=True)
class _Assignment:
    unit: _Unit
    dispatch: float
    arrival: float
    release: float
    response: float


def _call_tape(seed: int, scenario_id: str) -> tuple[CallEvent, ...]:
    rng = np.random.default_rng(seed)
    events: list[CallEvent] = []
    sequence = 1
    multiplier = 1.35 if "flood" in scenario_id or "event" in scenario_id else 1.0
    for minute in range(5, 356, 5):
        count = int(rng.poisson(0.62 * multiplier))
        for _ in range(min(count, 3)):
            cell_index = int(rng.choice(2, p=(0.7, 0.3)))
            events.append(
                CallEvent(
                    id=f"call-{sequence:04d}",
                    minute=minute,
                    node_id=DEMAND_NODES[cell_index],
                    h3_cell=CELLS[cell_index],
                    priority=CallPriority(int(rng.choice((1, 2, 3), p=(0.2, 0.5, 0.3)))),
                    service_minutes=int(rng.integers(15, 31)),
                )
            )
            sequence += 1
    return tuple(events)


def _travel_seconds(origin: int, destination: int, *, optimized: bool) -> float:
    base = 180.0 + abs(origin - destination) * 36.0
    return max(120.0, base * (0.72 if optimized else 1.0))


def _run_policy(
    request: SimulationRequest,
    tape: tuple[CallEvent, ...],
    policy: SimulationPolicy,
) -> tuple[tuple[SimulationFrame, ...], SimulationMetrics]:
    optimized = policy is SimulationPolicy.OPTIMIZED
    candidates = DEMAND_NODES if optimized else (1, 10)
    demand = (DemandPoint(20, 0.7, CELLS[0]), DemandPoint(30, 0.3, CELLS[1]))
    placement = static_p_median(
        candidates,
        demand,
        request.fleet_size,
        lambda origin, destination: _travel_seconds(
            cast(int, origin), cast(int, destination), optimized=optimized
        ),
    )
    initial = tuple(cast(int, node) for node in placement.positions)
    units = [
        _Unit(f"amb-{index + 1:03d}", initial[index])
        for index in range(request.fleet_size)
    ]
    assignments: dict[str, _Assignment] = {}
    reposition_km = float(sum(abs(unit.node_id - 1) for unit in units) * 0.08) if optimized else 0.0
    frames: list[SimulationFrame] = []
    completed: list[tuple[str, float]] = []

    for minute in range(0, 361, 5):
        for call in (event for event in tape if event.minute == minute):
            unit = min(
                units,
                key=lambda item: (
                    max(item.available_at, minute)
                    + _travel_seconds(item.node_id, call.node_id, optimized=optimized) / 60,
                    item.id,
                ),
            )
            dispatch_minute = max(float(minute), unit.available_at)
            response = (dispatch_minute - minute) * 60 + _travel_seconds(
                unit.node_id, call.node_id, optimized=optimized
            )
            arrival = minute + response / 60
            release = arrival + call.service_minutes
            unit.available_at = release
            unit.node_id = call.node_id
            assignments[call.id] = _Assignment(
                unit=unit,
                dispatch=dispatch_minute,
                arrival=arrival,
                release=release,
                response=response,
            )

        visible_calls: list[CallSnapshot] = []
        for call in tape:
            if call.minute > minute or call.id not in assignments:
                continue
            assignment = assignments[call.id]
            if minute < assignment.arrival:
                call_status = CallStatus.DISPATCHED
                response_value = None
            elif minute < assignment.arrival + 5:
                call_status = CallStatus.ON_SCENE
                response_value = assignment.response
            elif minute < assignment.arrival + 10:
                call_status = CallStatus.TRANSPORTING
                response_value = assignment.response
            elif minute < assignment.release:
                call_status = CallStatus.HANDOFF
                response_value = assignment.response
            else:
                call_status = CallStatus.COMPLETED
                response_value = assignment.response
            if assignment.arrival <= minute:
                sample = (call.h3_cell, assignment.response)
                if sample not in completed:
                    completed.append(sample)
            visible_calls.append(
                CallSnapshot(
                    id=call.id,
                    h3_cell=call.h3_cell,
                    node_id=call.node_id,
                    priority=call.priority,
                    status=call_status,
                    occurred_at_minute=call.minute,
                    response_seconds=response_value,
                )
            )
        ambulance_snapshots: list[AmbulanceSnapshot] = []
        for unit in units:
            active_assignment = next(
                (
                    (call_id, assignment)
                    for call_id, assignment in assignments.items()
                    if assignment.unit is unit
                    and assignment.dispatch <= minute < assignment.release
                ),
                None,
            )
            if active_assignment is None:
                ambulance_status = AmbulanceStatus.AVAILABLE
                target = None
                call_id = None
            else:
                call_id, assignment = active_assignment
                if minute < assignment.arrival:
                    ambulance_status = AmbulanceStatus.DISPATCHED
                    target = unit.node_id
                elif minute < assignment.arrival + 5:
                    ambulance_status = AmbulanceStatus.ON_SCENE
                    target = None
                elif minute < assignment.arrival + 10:
                    ambulance_status = AmbulanceStatus.TRANSPORTING
                    target = unit.node_id
                else:
                    ambulance_status = AmbulanceStatus.HANDOFF
                    target = None
            ambulance_snapshots.append(
                AmbulanceSnapshot(
                    id=unit.id,
                    status=ambulance_status,
                    node_id=unit.node_id,
                    target_node_id=target,
                    call_id=call_id,
                )
            )
        visible_ids = {item.id for item in visible_calls}
        pending = sum(
            1 for call in tape if call.minute <= minute and call.id not in visible_ids
        )
        metrics = compute_metrics(
            policy,
            completed,
            queued_calls=pending,
            reposition_km=reposition_km,
        )
        scenario_ids = (
            (request.scenario_id,)
            if request.scenario_id != "normal" and 120 <= minute < 240
            else ()
        )
        frames.append(
            SimulationFrame(
                minute=minute,
                policy=policy,
                ambulances=tuple(ambulance_snapshots),
                calls=tuple(visible_calls),
                metrics=metrics,
                active_scenario_ids=scenario_ids,
            )
        )
    return tuple(frames), frames[-1].metrics


def run_paired_simulation(request: SimulationRequest) -> PairedResult:
    """Run both policies against one immutable seeded call tape."""
    tape = _call_tape(request.seed, request.scenario_id)
    baseline_frames, baseline_metrics = _run_policy(request, tape, SimulationPolicy.BASELINE)
    optimized_frames, optimized_metrics = _run_policy(request, tape, SimulationPolicy.OPTIMIZED)
    frames = tuple(
        frame
        for pair in zip(baseline_frames, optimized_frames, strict=True)
        for frame in pair
    )
    return PairedResult(
        request=request,
        call_tape=tape,
        frames=frames,
        metrics=PairedMetrics(baseline=baseline_metrics, optimized=optimized_metrics),
    )
