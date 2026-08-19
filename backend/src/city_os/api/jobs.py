"""Bounded in-process simulation registry with replayable frames."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock

from city_os.contracts import (
    ApiError,
    MethodologyMetadata,
    SimulationFrame,
    SimulationJobResponse,
    SimulationJobStatus,
    SimulationRequest,
)
from city_os.simulation import PairedResult, run_paired_simulation


@dataclass(frozen=True, slots=True)
class Job:
    response: SimulationJobResponse
    frames: tuple[SimulationFrame, ...]


class JobRegistry:
    def __init__(self, capacity: int = 16) -> None:
        self.capacity = capacity
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._lock = RLock()

    def create(self, request: SimulationRequest) -> Job:
        simulation_id = f"sim-{request.seed}-{request.fleet_size}-{request.scenario_id}"
        try:
            result: PairedResult = run_paired_simulation(request)
            response = SimulationJobResponse(
                simulation_id=simulation_id,
                request=request,
                status=SimulationJobStatus.COMPLETED,
                metrics=result.metrics,
                methodology=MethodologyMetadata(
                    call_tape_seed=request.seed,
                    calibration_target_seconds=1260,
                    calibration_description=(
                        "Synthetic demand uses the published 21-minute ECHO mean only "
                        "as a calibration target. "
                        "All p90 values are empirical simulation outputs."
                    ),
                    data_label="simulated",
                ),
                error=None,
            )
            job = Job(response=response, frames=result.frames)
        except Exception as exc:  # registry converts engine failures into an explicit API state
            response = SimulationJobResponse(
                simulation_id=simulation_id,
                request=request,
                status=SimulationJobStatus.FAILED,
                metrics=None,
                methodology=None,
                error=ApiError(code="simulation_failed", message=str(exc)),
            )
            job = Job(response=response, frames=())
        with self._lock:
            self._jobs[simulation_id] = job
            self._jobs.move_to_end(simulation_id)
            while len(self._jobs) > self.capacity:
                self._jobs.popitem(last=False)
        return job

    def get(self, simulation_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(simulation_id)
