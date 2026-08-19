# City OS Data and Flow Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build versioned offline artifacts that turn São Paulo OSM roads and privacy-preserving camera counts into directed edge traffic state and H3 population density.

**Architecture:** Normalize a real OSMnx `MultiDiGraph` into stable nodes/arcs, map H3 resolution-8 cells to arcs, count directional class crossings from short-lived tracks, infer unobserved edge flow with graph-regularized constrained least squares, apply BPR travel time, and aggregate occupancy into H3 density. Every stage is deterministic and emits schema-validated artifacts consumed by Developer B.

**Tech Stack:** Python 3.12, Pydantic 2, OSMnx/NetworkX, GeoPandas/Shapely/H3, NumPy/SciPy, PyArrow, OpenCV, Ultralytics YOLO.

**Spec:** `docs/superpowers/specs/2026-08-19-ambulance-flow-allocation-design.md`; coordination: `docs/superpowers/plans/2026-08-19-city-os-parallel-integration.md`.

## Global Constraints

- Work only on `dev-a/data-flow` and owned directories listed in the integration plan.
- Tests use tiny local graphs and frames; no test may require network or a live camera.
- One-way OSM directions remain separate arcs. IDs and output ordering must be stable across runs.
- Vision output contains only aggregate class/direction/count/confidence buckets.

---

## Task 1: Normalize the Directed Road Graph and H3 Grid

**Files:**
- Create: `backend/src/city_os/spatial/__init__.py`
- Create: `backend/src/city_os/spatial/osm_graph.py`
- Create: `backend/src/city_os/spatial/h3_grid.py`
- Create: `backend/tests/spatial/test_osm_graph.py`
- Create: `backend/tests/spatial/test_h3_grid.py`

**Interfaces:** Consume an OSMnx `nx.MultiDiGraph` and municipal boundary; produce ordered `RoadNode`/`RoadEdge` records and H3 polygons matching the frozen contracts.

- [ ] Write a failing test with nodes `1,2,3`, forward arcs `1→2`, `2→3`, a reverse `2→1`, and parallel keys; assert every physical direction survives with a unique stable `edge_id`.
- [ ] Run `cd backend && uv run pytest tests/spatial/test_osm_graph.py -q`; confirm import failure.
- [ ] Implement `normalize_osm_graph(graph: nx.MultiDiGraph, resolution: int = 8) -> tuple[list[RoadNode], list[RoadEdge]]`, deriving free-flow seconds from OSM speed with a documented urban default and capacity from road class.
- [ ] Run the test and confirm pass, including identical IDs after reordered insertion.
- [ ] Write a failing boundary test asserting `build_h3_grid(boundary, resolution=8)` covers the boundary centroid, clips edge cells, and returns unique sorted cell IDs.
- [ ] Implement the minimum H3 conversion and GeoDataFrame output; run both tests.
- [ ] Commit: `feat: normalize directed OSM graph and H3 grid`

## Task 2: Build and Validate Spatial Artifacts

**Files:**
- Create: `backend/src/city_os/spatial/artifacts.py`
- Create: `backend/tests/spatial/test_artifacts.py`
- Create: `scripts/fetch_osm_extract.py`
- Create: `scripts/build_spatial_artifacts.py`
- Create: `scripts/build_map_tiles.sh`
- Create: `data/fixtures/flow/.gitkeep`

**Interfaces:** Produce `nodes.parquet`, `edges.parquet`, `h3_cells.geojson`, `edge_h3_weights.parquet`, `sao-paulo.pmtiles`, and `manifest.json` with schema version, row counts, bounds, source date/license, and checksums.

- [ ] Write a failing round-trip test that writes the Task 1 toy graph, reloads it, and asserts types, CRS `EPSG:4326`, checksums, and edge-to-H3 weights summing to `1 ± 1e-6` per edge.
- [ ] Run the test and confirm failure because `write_spatial_artifacts` does not exist.
- [ ] Implement `write_spatial_artifacts(output_dir, nodes, edges, cells) -> ArtifactManifest` using atomic temporary files and deterministic sorting.
- [ ] Implement an explicit build-time fetch CLI that downloads a pinned OSM PBF, verifies its configured SHA-256, clips it to the official municipal boundary, records the OpenStreetMap attribution/source date, and never runs during the demo.
- [ ] Implement spatial CLI arguments `--pbf`, `--boundary`, `--output`; forbid implicit downloads.
- [ ] Build `sao-paulo.pmtiles` from the same clipped PBF with pinned tilemaker/PMTiles container versions; add an acceptance check that tile bounds contain the municipal centroid and stay within the São Paulo region.
- [ ] Run `uv run pytest tests/spatial -q` and build the tiny committed fixture under `data/fixtures/flow/`.
- [ ] Commit: `feat: emit versioned spatial artifacts`

## Task 3: Count Directional Objects Without Identity Retention

**Files:**
- Create: `backend/src/city_os/vision/__init__.py`
- Create: `backend/src/city_os/vision/tracks.py`
- Create: `backend/src/city_os/vision/line_counter.py`
- Create: `backend/src/city_os/vision/detector.py`
- Create: `backend/src/city_os/vision/camera_config.py`
- Create: `backend/tests/vision/test_line_counter.py`
- Create: `backend/tests/vision/test_detector_adapter.py`
- Create: `scripts/process_camera_frames.py`
- Create: `data/fixtures/vision/provenance.json`

**Interfaces:** Consume timestamped detections/tracks and camera crossing-line config; emit only frozen `CameraObservation` five-minute aggregates.

- [ ] Write a failing test for one car crossing A→B, one person crossing B→A, a jittering track touching but not crossing, and an expired track; expect exactly two aggregate counts.
- [ ] Run `uv run pytest tests/vision/test_line_counter.py -q`; confirm failure.
- [ ] Implement signed-side crossing with hysteresis, minimum track age, confidence averaging, and deletion after a short TTL.
- [ ] Add a detector-adapter test with a fake YOLO result covering `person,bicycle,motorcycle,car,bus,truck`; reject all other classes.
- [ ] Implement `YoloDetector` with lazy Ultralytics import and dependency injection so tests need no model weights.
- [ ] Implement the offline CLI accepting a local video/image directory, local model path, camera config, and output Parquet path; never persist annotated frames by default.
- [ ] Add at least one authorized São Paulo sample clip/image sequence with source URL, retrieval date, license/terms note, camera location, and SHA-256 in `provenance.json`; store only the minimum clip needed for the demo.
- [ ] Manually count the sample's line crossings and add a fixture test requiring per-class/direction error within the documented MVP tolerance.
- [ ] Run `uv run pytest tests/vision -q` and inspect the output schema with PyArrow.
- [ ] Commit: `feat: aggregate privacy-safe camera crossings`

## Task 4: Infer Network Flow and Travel Time

**Files:**
- Create: `backend/src/city_os/flow/__init__.py`
- Create: `backend/src/city_os/flow/estimator.py`
- Create: `backend/src/city_os/flow/travel_time.py`
- Create: `backend/tests/flow/test_estimator.py`
- Create: `backend/tests/flow/test_travel_time.py`

**Interfaces:** Consume incidence matrix `B`, edge-line-graph Laplacian `L_E`, observation matrix `H`, observed counts `y`, prior `f_prev`; produce non-negative edge flows and BPR travel seconds.

- [ ] Write a failing chain/branch test for
  `argmin ||W(Hf-y)||² + λs fᵀL_Ef + λt||f-f_prev||² + λc||Bf-b||²`, asserting observed edges fit tolerance, all flows are non-negative, and internal-node residual is bounded.
- [ ] Run `uv run pytest tests/flow/test_estimator.py -q`; confirm failure.
- [ ] Implement `estimate_edge_flows(..., lambda_spatial, lambda_temporal, lambda_conservation) -> np.ndarray` using SciPy bounded least squares and deterministic sparse matrices.
- [ ] Add tests for no observations, low-confidence weighting, disconnected components, and identical repeated results.
- [ ] Write BPR tests asserting `t=t0` at zero flow, monotonic increase, finite overload behavior, and an explicit blocked-edge sentinel.
- [ ] Implement `bpr_travel_seconds(t0, flow, capacity, alpha=0.15, beta=4.0, blocked=None)` and run all flow tests.
- [ ] Commit: `feat: infer graph flow and BPR travel time`

## Task 5: Convert Edge State to H3 Density

**Files:**
- Create: `backend/src/city_os/flow/density.py`
- Create: `backend/tests/flow/test_density.py`
- Create: `scripts/build_flow_artifacts.py`

**Interfaces:** Consume edge flow/travel state, class composition, and edge-H3 overlap weights; produce `edge_state.parquet` and `h3_density.parquet` using frozen schemas.

- [ ] Write a failing test with two edges split across two cells; convert vehicle classes using fixed occupancy priors and assert total inferred people is conserved after spatial allocation.
- [ ] Run the density test and confirm failure.
- [ ] Implement `aggregate_h3_density(edge_states, edge_h3_weights, cell_areas_km2, occupancy_priors) -> list[H3Density]` with confidence propagation and zero-filled cells.
- [ ] Add emergency intensity as a normalized, configurable function of resident/flow density; test bounded non-negative output and stable ordering.
- [ ] Implement `build_flow_artifacts.py --spatial-manifest --observations --output` and include source checksums and estimator parameters in its manifest.
- [ ] Run `uv run pytest tests/flow -q` and build the committed two-district fixture.
- [ ] Commit: `feat: aggregate network occupancy into H3 density`

## Task 6: Data-Lane Acceptance Gate

**Files:**
- Modify: `data/fixtures/flow/manifest.json`
- Create: `backend/tests/flow/test_fixture_acceptance.py`

- [ ] Validate every artifact against Developer B's frozen Pydantic/schema definitions; do not create local duplicates.
- [ ] Assert every reachable H3 cell maps to at least one graph node and every `edge_state.edge_id` exists in the road artifact.
- [ ] Assert observed-direction counts influence the matching directed arc, not its reverse.
- [ ] Verify `sao-paulo.pmtiles` and the road graph came from the same pinned OSM extract and publish the required OpenStreetMap attribution to C.
- [ ] Run `uv run pytest tests/spatial tests/vision tests/flow -q` twice and compare generated checksums.
- [ ] Run `rg -n "face|mac.address|identity|TODO|FIXME|placeholder" backend/src/city_os/{spatial,vision,flow} scripts/build_*`; resolve unsafe or incomplete hits.
- [ ] Publish manifest path, schema version, checksum list, and build command to the integrator.
- [ ] Commit: `test: verify deterministic City OS flow artifacts`
