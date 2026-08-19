# City OS Simulation and API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide frozen cross-team contracts and a deterministic paired ambulance simulation/API that demonstrates reduced p90 response under dynamic allocation.

**Architecture:** A seeded event tape drives two isolated worlds: a competent static p-median baseline and a receding-horizon CVaR90 optimizer. Both use the same directed travel-time graph, calls, fleet, service-time draws, and scenario shocks. FastAPI exposes bootstrap data, scenario parsing, simulation creation/status, and WebSocket frames.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, NumPy/SciPy, NetworkX, GeoPandas/H3, PyArrow, pytest, Hypothesis.

**Spec:** `docs/superpowers/specs/2026-08-19-ambulance-flow-allocation-design.md`; coordination: `docs/superpowers/plans/2026-08-19-city-os-parallel-integration.md`.

## Global Constraints

- Developer B owns the backend scaffold and frozen schemas; publish Task 1 before continuing.
- Baseline and optimized runs must share the exact immutable call/service/scenario tape.
- The published 21-minute priority-1/ECHO mean calibrates the synthetic baseline; p90 remains explicitly simulated.
- Optimization must finish within the compressed-demo budget and use deterministic tie-breaking.

---

## Task 1: Scaffold Backend and Freeze Contracts — C0 Gate

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/city_os/__init__.py`
- Create: `backend/src/city_os/contracts/__init__.py`
- Create: `backend/src/city_os/contracts/api.py`
- Create: `backend/src/city_os/contracts/artifacts.py`
- Create: `backend/src/city_os/contracts/export_schema.py`
- Create: `backend/tests/contracts/test_contracts.py`
- Create: `backend/schema/city-os.schema.json`
- Create: `backend/tests/fixtures/contracts/bootstrap.json`
- Create: `backend/tests/fixtures/contracts/stream.jsonl`

**Interfaces:** Export every model listed in the integration plan, JSON Schema, one bootstrap fixture, and at least three frames per policy.

- [ ] Configure Python 3.12, package discovery, Ruff, mypy, pytest, and all backend dependencies up front to avoid shared-file edits by A.
- [ ] Write failing validation tests for enums, positive fleet size, H3 strings, metric percentages `0..100`, monotonic scenario dates, and rejected unknown fields.
- [ ] Run `cd backend && uv run pytest tests/contracts -q`; confirm failure.
- [ ] Implement strict Pydantic models, `AmbulanceStatus`, scenario/source/policy enums, and artifact manifest/checksum models.
- [ ] Export deterministic JSON Schema and fixtures; add a test that regeneration produces no diff.
- [ ] Run pytest, Ruff, and mypy; share the commit SHA with A and C and pause for their contract acknowledgement.
- [ ] Commit: `chore: scaffold backend and freeze MVP contracts`

## Task 2: Parse Scenario Cards and Generate the Immutable Call Tape

**Files:**
- Create: `backend/src/city_os/scenarios/parser.py`
- Create: `backend/src/city_os/scenarios/fallback.py`
- Create: `backend/src/city_os/demand/call_tape.py`
- Create: `backend/tests/scenarios/test_parser.py`
- Create: `backend/tests/demand/test_call_tape.py`

**Interfaces:** `parse_scenario_card(text, llm_client=None) -> ScenarioObservation`; `generate_call_tape(density, scenarios, seed, duration_minutes=360) -> tuple[CallEvent, ...]`.

- [ ] Write parser tests for flood, stadium event, and blocked avenue text; fake malformed/timeout LLM output and require deterministic fallback JSON with lower confidence.
- [ ] Implement typed validation and fallback rules; no internet dependency in normal demo operation.
- [ ] Write a failing demand test for inhomogeneous Poisson draws `λ(h,t)=base(h,t)×scenario_multiplier(h,t)`, stable seed/order/IDs, and elevated calls only in affected cells/time.
- [ ] Implement seeded `numpy.random.Generator`, priority mix, service-time draws, and nearest reachable graph-node snapping.
- [ ] Add calibration test asserting many seeded baseline samples average `21 minutes ± 90 seconds` for priority-1/ECHO after scale calibration.
- [ ] Run `uv run pytest tests/scenarios tests/demand -q`.
- [ ] Commit: `feat: generate deterministic scenario call tapes`

## Task 3: Implement Routing and Ambulance Lifecycle

**Files:**
- Create: `backend/src/city_os/routing/travel_time.py`
- Create: `backend/src/city_os/simulation/entities.py`
- Create: `backend/src/city_os/simulation/events.py`
- Create: `backend/src/city_os/simulation/dispatch.py`
- Create: `backend/tests/routing/test_travel_time.py`
- Create: `backend/tests/simulation/test_lifecycle.py`

**Interfaces:** `TravelTimeProvider.shortest_seconds(source, target, minute, scenario_ids) -> float`; event transitions among all seven frozen ambulance states.

- [ ] Write routing tests on a directed diamond graph showing one-way behavior, time-bucket changes, blocked-edge rerouting, and unreachable pairs.
- [ ] Implement cached Dijkstra keyed by source, five-minute bucket, and active scenario signature.
- [ ] Write lifecycle tests from `AVAILABLE → DISPATCHED → ON_SCENE → TRANSPORTING → HANDOFF → RELEASED → AVAILABLE`, plus `REPOSITIONING` preemption by a call.
- [ ] Implement a priority queue with stable `(time, priority, sequence)` ordering and nearest-available dispatch with priority-aware queues.
- [ ] Assert response seconds are call-to-arrival, not call-to-dispatch, and no ambulance serves overlapping calls.
- [ ] Run routing and lifecycle tests.
- [ ] Commit: `feat: simulate routing dispatch and ambulance lifecycle`

## Task 4: Implement Baseline and CVaR90 Allocation

**Files:**
- Create: `backend/src/city_os/optimization/baseline.py`
- Create: `backend/src/city_os/optimization/cvar.py`
- Create: `backend/src/city_os/optimization/reposition.py`
- Create: `backend/tests/optimization/test_baseline.py`
- Create: `backend/tests/optimization/test_cvar.py`

**Interfaces:** `static_p_median(candidates, demand, fleet_size, travel) -> Allocation`; `optimize_positions(snapshot, forecast, candidates, config) -> Allocation`.

- [ ] Write toy p-median tests proving deterministic placement and that fleet multiplicity totals the requested slider value.
- [ ] Implement a competent static baseline using average historical demand only; compute it once per simulation.
- [ ] Write an exhaustive tiny-world oracle for objective `CVaR90(response)+λr·reposition_km+λe·equity_gap`; assert the chosen allocation matches the oracle.
- [ ] Implement candidate pruning, greedy initialization, deterministic local swaps, capacity constraints, reachable-node snapping, and a time limit that returns the best incumbent.
- [ ] Add anti-thrashing tests: minimum dwell, improvement threshold, maximum move distance, and dispatched-unit exclusion.
- [ ] Run `uv run pytest tests/optimization -q`; benchmark the bundled candidate count under the 15-minute simulated cadence.
- [ ] Commit: `feat: optimize ambulance positions with CVaR90`

## Task 5: Run Paired Simulations and Compute Metrics

**Files:**
- Create: `backend/src/city_os/simulation/engine.py`
- Create: `backend/src/city_os/simulation/paired.py`
- Create: `backend/src/city_os/simulation/metrics.py`
- Create: `backend/tests/simulation/test_paired.py`
- Create: `backend/tests/simulation/test_metrics.py`

**Interfaces:** `run_paired_simulation(request, world) -> PairedSimulationResult`; stream ordered `SimulationFrame` objects at five-minute intervals for each policy.

- [ ] Write metric tests with exact response samples and hand-computed mean, p50, p90, p95, service-level percentages, queued/unserved, worst-district p90, and reposition km.
- [ ] Write a paired test asserting identical call IDs/times/service draws and fleet size across policies while allowing dispatch/allocation to differ.
- [ ] Implement two isolated engines from the same frozen tape; reoptimize at minute `0`, every `15`, and immediately on scenario activation.
- [ ] Emit 72 five-minute frames per policy for six hours, plus a terminal frame; use simulated clock only.
- [ ] Add determinism test comparing two seed-42 serialized results and an invariant/property test for no negative times or duplicate active assignments.
- [ ] Run `uv run pytest tests/simulation -q` and profile until the paired fixture completes under 50 seconds, leaving UI startup margin.
- [ ] Commit: `feat: run paired ambulance allocation simulations`

## Task 6: Expose FastAPI and WebSocket Streaming

**Files:**
- Create: `backend/src/city_os/api/app.py`
- Create: `backend/src/city_os/api/dependencies.py`
- Create: `backend/src/city_os/api/jobs.py`
- Create: `backend/src/city_os/api/routes.py`
- Create: `backend/src/city_os/api/websocket.py`
- Create: `backend/tests/api/test_routes.py`
- Create: `backend/tests/api/test_websocket.py`

**Interfaces:** Implement the five endpoints fixed in the design spec and `/healthz`; frames conform exactly to Task 1 schema.

- [ ] Write failing TestClient tests for bootstrap, scenario parse, create/get simulation, invalid fleet/seed/scenario, missing job, and health.
- [ ] Implement an in-process bounded job registry and background execution appropriate to a single-demo process; expose explicit `queued/running/completed/failed` status.
- [ ] Write a WebSocket test asserting baseline and optimized frames, monotonically increasing minutes per policy, terminal metrics, and clean close.
- [ ] Implement stream replay for a client connecting after job start and a capped frame buffer.
- [ ] Add structured error bodies; never silently replace corrupt artifacts or optimizer exceptions.
- [ ] Run `uv run pytest tests/api -q`, then full pytest/Ruff/mypy.
- [ ] Commit: `feat: expose City OS simulation API`

## Task 7: Backend Acceptance Gate

**Files:**
- Create: `backend/tests/api/test_vertical_slice.py`
- Modify: `backend/tests/fixtures/contracts/stream.jsonl`

- [ ] Load Developer A's two-district manifest and run a seed-42 paired simulation through HTTP and WebSocket.
- [ ] Assert optimized p90 is lower than baseline p90 for the demo fixture without modifying metrics after simulation.
- [ ] Regenerate JSON Schema/fixtures and notify C of the exact schema checksum.
- [ ] Run `uv lock --check`, full pytest, Ruff, mypy, and the six-hour performance check.
- [ ] Run `rg -n "TODO|FIXME|placeholder|random\.random|requests\.|httpx\." backend/src`; resolve incomplete or accidental online behavior.
- [ ] Publish startup command, artifact path, seed, frame count, runtime, and metrics to the integrator.
- [ ] Commit: `test: verify deterministic paired simulation API`
