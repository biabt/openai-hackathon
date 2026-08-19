# Ambulance Flow Allocation MVP — Design Specification

**Date:** 2026-08-19  
**Status:** Approved design, ready for implementation planning  
**Context:** Hackathon decision-support simulation for the municipality of São Paulo

## 1. Product objective

Build a reproducible simulation showing how predictive ambulance positioning can reduce the 90th-percentile emergency response time in São Paulo.

The system uses a real OpenStreetMap road graph and real observable mobility signals where available. It converts sparse directional flow observations into a graph-wide flow estimate, aggregates network occupancy into H3 density, generates transparent synthetic emergency calls, and compares two policies under identical conditions:

1. **Before:** a calibrated static ambulance-positioning policy representing current-style non-predictive operations.
2. **After:** an event-aware dynamic positioning policy minimizing tail response time.

The main demonstration is counterfactual. It does not claim to reproduce the actual SAMU dispatch system or recommend real clinical action.

## 2. Success criteria

The MVP succeeds when it can:

- Render São Paulo using real OSM geometry.
- Show directional camera-derived counts on mapped road edges.
- Produce a time-varying citywide flow field with uncertainty.
- Aggregate the inferred network state into H3 resolution 8 density.
- Run the same seeded six-hour call tape through baseline and optimized policies.
- Reposition a slider-controlled fleet to any eligible city road location.
- Activate simulated event and flood cards that alter demand and travel costs.
- Report an improved empirical p90 response time without hiding movement cost or geographic inequity.
- Replay the judged scenario deterministically without depending on live external services.
- Complete a six-hour paired simulation in approximately 60 seconds and each optimization step in under three seconds on the demo machine.

## 3. Non-goals

- Live clinical dispatch or integration with SAMU systems.
- Patient diagnosis, medical triage, or ambulance capability matching.
- Identification or tracking of people from cameras.
- A claim that inferred people density is a census-quality measurement.
- A full traffic assignment or microscopic mobility simulator.
- Internet-scale event discovery during the judged demo.
- Exact reconstruction of real ambulance bases, calls, or response-time distributions.

## 4. Fixed MVP decisions

- **Geography:** municipality of São Paulo.
- **Road model:** directed OSM multigraph; each permitted direction is a separate edge.
- **Analysis grid:** H3 resolution 8.
- **Flow aggregation interval:** five simulated minutes.
- **Simulation duration:** six hours, compressed to roughly 60 seconds.
- **Optimization interval:** every 15 simulated minutes and immediately after a scenario-state change.
- **Forecast horizon:** 60 simulated minutes.
- **Fleet:** adjustable slider; one ambulance capability class.
- **Placement:** any eligible H3 cell, snapped to a reachable OSM road node.
- **Primary metric:** empirical 90th-percentile response time.
- **Optimization surrogate:** CVaR at alpha 0.90.
- **Calibration benchmark:** the synthetic priority-1/ECHO baseline is calibrated to the municipality's published 2024 mean response-time value of 21 minutes; p90 remains a simulated outcome, not a published baseline statistic.
- **Calls:** synthetic and seeded; inputs and outputs visibly labeled as simulated or inferred.
- **Events:** predefined natural-language scenario cards parsed into a typed observation schema.
- **Data store:** versioned Parquet, GeoJSON, JSON, and PMTiles artifacts; no operational database.

## 5. Architecture

The project has six independently testable subsystems.

### 5.1 Spatial preprocessing

Responsibilities:

- Obtain the São Paulo municipal boundary.
- Download and simplify the OSM drivable network.
- Preserve directed connectivity and relevant OSM attributes.
- Create the H3 r8 city grid.
- Map H3 cells, cameras, facilities, and scenario geometries to road nodes and edges.
- Generate a bundled OSM-derived basemap artifact for the portal.

Outputs:

- `road_nodes.parquet`
- `road_edges.parquet`
- `h3_cells.parquet`
- `h3_to_nodes.parquet`
- `camera_edge_map.json`
- `sao_paulo.pmtiles` or an equivalent bundled OSM-derived layer

### 5.2 Vision ingestion

Responsibilities:

- Read recorded CET camera frame sequences.
- Detect `person`, `bicycle`, `motorcycle`, `car`, `bus`, and `truck` using a small Ultralytics YOLO model.
- Track detections for only the short interval necessary to avoid double counting.
- Count directional crossings through per-camera regions of interest and counting lines.
- Aggregate counts into five-minute buckets with confidence and quality fields.
- Discard identities; never perform facial recognition or cross-camera re-identification.

The judged demo uses bundled frames and cached detections. A live-frame adapter is optional and cannot be required for the demo.

Outputs:

- `camera_observations.parquet`
- `camera_quality.parquet`
- optional annotated sample clips for validation only

### 5.3 Network flow and density engine

Responsibilities:

- Fuse sparse camera counts, SPTrans speed observations when present, OSM priors, and temporal continuity.
- Estimate directional edge flow, speed, travel time, occupancy, and confidence.
- Respect approximate flow conservation at internal road nodes.
- Aggregate mode-weighted edge occupancy into H3 people-density estimates.

Outputs:

- `edge_state_<scenario>.parquet`
- `h3_density_<scenario>.parquet`
- `travel_cost_<time_bucket>.npz`

### 5.4 Scenario sensor

Responsibilities:

- Present predefined natural-language cards representing events or disruptions.
- Use an LLM structured-output call to extract a typed observation.
- Validate geometry, time range, multiplier bounds, and source labeling.
- Fall back to a stored JSON observation when the model is unavailable or invalid.
- Apply observations to demand intensity and/or road accessibility.

The LLM interprets evidence. It never calculates travel time, generates response metrics, or chooses ambulance placements.

### 5.5 Demand, optimization, and simulation engine

Responsibilities:

- Generate a seeded emergency-call tape from time-varying H3 intensity.
- Maintain ambulance lifecycle state.
- Dispatch the minimum-ETA available or repositioning ambulance.
- Run isolated baseline and optimized simulations against the same event tape.
- Reposition idle ambulances using a time-bounded CVaR local-search solver.
- Stream time, calls, ambulance movements, and metrics to the portal.

### 5.6 Command portal

Responsibilities:

- Render OSM streets, H3 density, edge flow, uncertainty, cameras, calls, ambulance paths, and event effects.
- Provide scenario selection, fleet-size slider, playback controls, and layer toggles.
- Show before/after metrics and distributions.
- Explain each event card and recommended repositioning.
- Label real, inferred, and synthetic data at the layer and metric level.

## 6. Data model and mathematics

### 6.1 Directed road graph

Let:

\[
G=(V,E)
\]

be a directed multigraph. Each edge \(e\in E\) stores:

\[
(u_e,v_e,\ell_e,\tau^0_e,c_e,k_e,\text{geometry}_e)
\]

where \(\ell_e\) is length, \(\tau^0_e\) is free-flow travel time, \(c_e\) is approximate capacity, and \(k_e\) is road class. Opposing legal directions are represented by separate edges.

### 6.2 Camera observations

For a camera mapped to directed edge \(e\), the observed flow for class \(m\) is:

\[
q^{cam}_{e,m,t}=\frac{1}{\Delta t}\sum_o \mathbb{1}[o\text{ crosses the line for }e\text{ during }t]
\]

Counts include a quality score derived from frame availability, detector confidence, occlusion, lighting, and camera stability.

### 6.3 Graph-constrained flow inference

Let \(f_t\ge 0\) be the unknown directional edge-flow vector, \(y_t\) the available observations, \(H_t\) the sensor-to-edge observation matrix, \(W_t\) confidence weights, \(B\) the node-edge incidence matrix, and \(L_E\) a line-graph Laplacian.

Estimate:

\[
\hat f_t = \arg\min_{f\ge0}
\|W_t(H_tf-y_t)\|_2^2
+\lambda_s f^T L_E f
+\lambda_t\|f-\hat f_{t-1}\|_2^2
\]

subject to approximate conservation:

\[
\|Bf-b_t\|_2\le\epsilon
\]

The boundary vector \(b_t\) allows net sources and sinks at graph boundaries and major activity zones. The estimator must output residuals and confidence; it must not present unobserved edges as directly measured.

### 6.4 Travel time

Use observed speed where reliable. Otherwise use the Bureau of Public Roads function:

\[
\tau_e(t)=\tau^0_e\left[1+0.15\left(\frac{\hat f_e(t)}{c_e}\right)^4\right]
\]

Scenario effects modify this cost:

\[
\tau'_e(t)=
\begin{cases}
\infty, & e\text{ blocked}\cr
\tau_e(t)(1+\delta_e(t)), & e\text{ degraded}\cr
\tau_e(t), & \text{otherwise}
\end{cases}
\]

### 6.5 Edge occupancy and H3 density

Approximate occupancy on edge \(e\):

\[
n_e(t)=\hat f_e(t)\tau_e(t)
\]

For H3 cell \(h\) with area \(A_h\):

\[
\rho_{h,t}=\frac{1}{A_h}\sum_e \omega_{he}\kappa_e n_e(t)
\]

where \(\omega_{he}\) is the proportion of edge occupancy assigned to the cell and \(\kappa_e\) is a conservative mode-specific people-per-vehicle factor. Pedestrian camera counts enter separately rather than being converted from vehicles.

The density layer is an activity proxy used for demand modeling, not a claim of exact population.

### 6.6 Synthetic emergency intensity

For each H3 cell:

\[
\log\lambda_h(t)=\beta_0+\beta^Tz_{h,t}+u_h+s(t)+\sum_r\gamma_rK_r(h,t)
\]

where \(z\) includes activity density, static population/land-use priors, transit accessibility, and time features; \(u_h\) is a spatial effect; \(s(t)\) captures periodicity; and \(K_r\) is a scenario-card kernel.

Calls are generated with a seeded Poisson process:

\[
N_{h,t}\sim \operatorname{Poisson}(\lambda_h(t)\Delta t)
\]

If calibration reveals strong overdispersion, a negative-binomial generator may replace Poisson without changing downstream interfaces.

### 6.7 Dynamic ambulance positioning

Let \(S\) be forecast call scenarios, \(T_s(x)\) the response time under placement \(x\), \(R(x,x_{prev})\) repositioning cost, \(p\) the fleet size, and \(\alpha=0.90\).

Optimize the CVaR surrogate:

\[
\min_{x,\eta}
\eta+\frac{1}{(1-\alpha)|S|}\sum_{s\in S}[T_s(x)-\eta]_+
+\lambda_RR(x,x_{prev})
+\lambda_EE(x)
\]

subject to:

\[
\sum_i x_i=p,\qquad x_i\in\mathbb{Z}_{\ge0}
\]

\(E(x)\) penalizes poor service in the worst-covered districts. The portal reports empirical p90 directly; CVaR is the solver objective because it is more stable under sampled demand.

The solver operates on a reduced candidate set of eligible H3 r8 cells and snaps results to reachable road nodes. Candidate reduction retains high-demand cells, geographically dispersed cells, hospitals, and current ambulance locations. A seeded greedy initialization plus swap/local search is preferred over a large mixed-integer solve because it can honor the three-second demo budget.

## 7. Baseline and experiment design

### 7.1 Static baseline

The baseline is deliberately credible rather than deliberately weak:

- Build a static placement from long-run average synthetic demand using a p-median-style heuristic.
- Do not use the upcoming event card or short-horizon forecast.
- After release, ambulances return toward their assigned static positions.
- Calibrate global dispatch/service delay parameters so the mean priority-1/ECHO response time matches the published 2024 municipal value of 21 minutes.

The benchmark comes from the municipality's 2026–2029 planning material, which identifies a 2024 base value of 21 minutes for extreme-severity ECHO occurrences: [Participa Mais São Paulo planning proposal](https://participemais.prefeitura.sp.gov.br/legislation/processes/340/draft_versions/70). The benchmark and calibration method must be shown in the portal or methodology panel. The system must not claim that static positions are actual SAMU positions or that a published p90 value exists.

### 7.2 Optimized policy

- Forecast the next 60 minutes from current density and active scenario observations.
- Recompute placement every 15 minutes or upon a disruption.
- Move only available ambulances.
- Allow repositioning ambulances to be dispatched.
- Apply minimum-benefit, minimum-dwell, and movement-cost rules to prevent thrashing.

### 7.3 Paired simulation

Both policies receive the same:

- Call timestamps and locations.
- Priority labels.
- Scene, transport, and handoff durations.
- Traffic transitions.
- Scenario-card activation times.
- Fleet size.

Separate state objects prevent policy leakage. Common random numbers reduce comparison variance.

## 8. Ambulance lifecycle

States:

1. `AVAILABLE`
2. `REPOSITIONING`
3. `DISPATCHED`
4. `ON_SCENE`
5. `TRANSPORTING`
6. `HANDOFF`
7. `RELEASED`, immediately transitioning to `AVAILABLE` at the scene or hospital node

On call arrival:

\[
a^*=\arg\min_{a\in A_{available}\cup A_{repositioning}}
\operatorname{ETA}(a,call\mid G,\tau(t))
\]

If no unit is dispatchable, the call enters a priority queue. The MVP uses one ambulance capability class; priority affects queue order and seeded duration distributions, not clinical decisions.

Fleet conservation and exclusive assignment are hard invariants.

## 9. Scenario-card contract

Every card has natural-language text plus a stored reference JSON object:

```json
{
  "id": "flood-aricanduva-1730",
  "type": "flood",
  "starts_at": "17:30",
  "ends_at": "19:00",
  "affected_h3": ["88a8100c05fffff"],
  "demand_multiplier": 1.25,
  "travel_penalty": 2.0,
  "blocked_edges": [12345, 12346],
  "confidence": 0.9,
  "source": "simulated"
}
```

Validation rules:

- Card type must be in the supported enumeration.
- End must follow start.
- H3 cells and edges must exist in bundled artifacts.
- Demand multiplier must be between 0.5 and 5.0.
- Travel penalty must be at least 1.0 and at most 10.0.
- Confidence must be between 0 and 1.
- Source must be `simulated` for the hackathon cards.

Initial cards:

- Concert/event near Allianz Parque.
- Flood disruption along Aricanduva.
- Optional demonstration or transit disruption in the central region.

## 10. Portal design

### 10.1 Map

The main view is a MapLibre map with:

- OSM-derived streets.
- H3 demand-density layer.
- Edge-flow and uncertainty layers.
- Camera locations and observed directions.
- Ambulance current positions, routes, and recommendations.
- Active calls and queue state.
- Event and flood geometries.

### 10.2 Controls

- Scenario selector.
- Fleet-size slider.
- Run/reset controls.
- Timeline scrubber and playback speed.
- Before/After toggle or synchronized comparison.
- Layer visibility controls.
- Deterministic seed display.

### 10.3 Metrics

- Primary: p90 response time.
- Mean, p50, and p95.
- Percentage served within 8, 12, and 20 minutes.
- Worst-district p90 and district distribution.
- Queued and unserved calls.
- Repositioning distance.
- Ambulance busy ratio.

Illustrative wireframe values must be replaced by computed values.

### 10.4 Demo sequence

1. Show real OSM roads, camera sites, and inferred normal-weekday density.
2. Run the paired normal scenario and reveal the first before/after distribution.
3. Activate the concert card and show the future hotspot plus preventive movement.
4. Activate the flood card and show blocked roads, changed ETAs, and a new placement.
5. Change fleet size and show how p90 and worst-district coverage respond.

## 11. Technical stack

### Frontend

- React with Next.js and TypeScript.
- MapLibre GL JS for the OSM-derived basemap.
- deck.gl for H3, paths, and high-volume spatial overlays.
- A lightweight chart library for response-time distributions and KPIs.

### Backend and modeling

- Python and FastAPI.
- Pydantic for API and scenario-card contracts.
- OSMnx and NetworkX for graph preparation and routing prototypes.
- GeoPandas and Shapely for spatial preprocessing.
- H3 Python bindings.
- NumPy, SciPy, and sparse matrices for flow inference and travel matrices.
- Ultralytics YOLO small model and OpenCV for recorded-frame processing.
- Parquet/GeoJSON/NPZ artifacts loaded into memory at startup.

### Runtime interfaces

- `GET /api/bootstrap` — metadata, bounds, scenarios, layer URLs, default seed.
- `POST /api/simulations` — create paired run with scenario, fleet size, and seed.
- `GET /api/simulations/{id}` — final metrics and methodology metadata.
- `WS /api/simulations/{id}/stream` — simulated clock, calls, units, movements, and metrics.
- `POST /api/scenario-cards/parse` — structured LLM extraction with deterministic fallback.

## 12. Offline-first behavior and error handling

- Bundle the preprocessed OSM graph and map layer.
- Bundle recorded camera samples and cached detection counts.
- Bundle all reference scenario JSON.
- Seed all stochastic processes.
- If LLM parsing fails schema validation, show the error and use the stored card.
- If the optimizer exceeds its time budget, keep the last feasible placement and mark the step degraded.
- If a call is unreachable because of closures, queue it and expose the reason.
- If camera data is missing, lower confidence and rely more heavily on temporal/graph priors.
- If a frame is stale or the camera moves, reject or down-weight the observation.
- If an API stream disconnects, the portal reconnects and requests the current simulation snapshot.
- No failure path may silently replace computed results with illustrative values.

## 13. Verification strategy

### 13.1 Vision

- Manually annotate directional crossings for short representative clips.
- Compare counts by object class and direction.
- Verify that track IDs expire and cannot link people across cameras.
- Verify stale, dark, obstructed, or shifted frames receive reduced quality.

### 13.2 Mathematics and spatial processing

- Assert nonnegative flows.
- Assert conservation residual remains within configured tolerance.
- Verify BPR travel time is monotonic in flow and infinite for blocked edges.
- Verify H3 weights conserve assigned occupancy within numerical tolerance.
- Withhold one observed camera edge and measure reconstruction error.
- Verify every candidate placement snaps to a reachable road node inside the municipality.

### 13.3 Simulation invariants

- Total ambulances remain equal to the slider-selected fleet.
- An ambulance cannot serve two calls simultaneously.
- Every state transition follows the lifecycle.
- Baseline and optimized simulations consume byte-identical event tapes.
- Resetting with the same seed reproduces identical metrics.
- Closures affect both policies identically.

### 13.4 Optimization

- Compare the solver against exhaustive search on toy graphs.
- Verify returned placement is feasible.
- Verify objective does not worsen relative to its greedy initialization.
- Test zero-demand, single-hotspot, disconnected, and fleet-larger-than-candidates cases.
- Record solver runtime and timeout behavior.

### 13.5 End-to-end acceptance

- Project starts from documented commands on a clean machine.
- Portal renders bundled São Paulo data without network access.
- Default paired scenario finishes within the performance budget.
- Metrics shown in the portal equal backend output.
- Event activation visibly changes density and/or travel cost.
- The optimized policy changes placement and reports p90, coverage, equity, and movement cost.

## 14. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Sparse cameras cannot identify all city flows | Show uncertainty; use cameras as constraints/calibration rather than claiming complete observation |
| Camera viewpoint changes | Per-camera ROI, stability check, cached judged-demo detections |
| Vehicle flow is not people flow | Use conservative mode factors, pedestrian counts, static priors, and explicit proxy labeling |
| Synthetic calls appear arbitrary | Publish the intensity equation, seed, calibration target, and scenario multipliers |
| Baseline is unfairly weak | Use a competent static p-median baseline and identical event tapes |
| Dynamic solver is slow | Reduce candidates, cache routing, use greedy plus local search, enforce time budget |
| Repositioning churn creates unrealistic gains | Movement cost, minimum benefit, dwell time, and dispatchable en-route units |
| External service breaks during judging | Bundle OSM, detections, scenarios, and event tapes; maintain deterministic fallback |
| Medical interpretation is overstated | Keep one capability class and label the system as operations research, not clinical decision-making |

## 15. Deliverables

- Reproducible preprocessing pipeline and versioned city artifacts.
- Camera detection/counting pipeline plus validated sample output.
- Flow/density inference module.
- Typed simulated LLM-sensor cards.
- Seeded discrete-event simulator.
- Baseline and dynamic positioning policies.
- FastAPI runtime with streamable paired simulations.
- Map-based command portal.
- Automated verification suite.
- Demo seed and three-minute presentation script.
- Methodology page explaining real, inferred, and simulated layers.
