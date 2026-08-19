# City OS Command Portal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a polished offline command portal that visualizes São Paulo flow/density and clearly demonstrates baseline-versus-optimized ambulance p90 response.

**Architecture:** A Next.js single-page portal renders local MapLibre/PMTiles geography and deck.gl layers. A typed transport supports frozen fixtures during parallel work and the local FastAPI/WebSocket service at integration. A reducer owns deterministic playback, policy frames, controls, scenario activation, and metrics.

**Tech Stack:** Next.js, React, TypeScript strict mode, MapLibre GL JS, deck.gl, PMTiles, Zod, JSON-schema-generated types, Vitest, React Testing Library, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-19-ambulance-flow-allocation-design.md`; coordination: `docs/superpowers/plans/2026-08-19-city-os-parallel-integration.md`.

## Global Constraints

- Work only within `frontend/` on `dev-c/portal`.
- Begin against Developer B's C0 schema and fixtures; never hand-copy backend interfaces.
- The real São Paulo basemap and all demo assets are local. No runtime web fonts, tile servers, analytics, or APIs.
- The primary visual result is p90 before/after; mean is contextual, never substituted.

---

## Task 1: Scaffold the Portal and Generated Contracts

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/page.tsx`
- Create: `frontend/src/app/globals.css`
- Create: `frontend/scripts/generate-contracts.mjs`
- Generate: `frontend/src/lib/contracts/generated.ts`
- Create: `frontend/src/lib/contracts/fixtures/bootstrap.json`
- Create: `frontend/src/lib/contracts/fixtures/stream.jsonl`
- Create: `frontend/src/lib/contracts/validate.ts`
- Create: `frontend/src/lib/api/transport.ts`
- Create: `frontend/src/lib/api/mock-transport.ts`
- Create: `frontend/src/lib/api/http-transport.ts`
- Create: `frontend/src/lib/api/transport.test.ts`

**Interfaces:** Generate TypeScript from C0 JSON Schema; both transports implement `CityOsTransport` for bootstrap, parse, create/status, and frame subscription.

- [ ] Configure strict TypeScript, ESLint, Vitest/jsdom, Testing Library, Playwright, and `contracts:generate`/`contracts:check` scripts.
- [ ] Make `contracts:generate` deterministically materialize B's versioned fixtures into the C-owned fixture directory; write a failing contract test that validates them and rejects an unknown ambulance status.
- [ ] Generate types directly from `../backend/schema/city-os.schema.json` and implement Zod/Ajv runtime validation at transport boundaries.
- [ ] Write parity tests that mock fetch/WebSocket and assert both transports produce identical typed domain messages.
- [ ] Run `npm test`, `npm run typecheck`, and `npm run contracts:check`.
- [ ] Commit: `chore: scaffold typed City OS portal`

## Task 2: Render the Offline São Paulo Map and Layers

**Files:**
- Create: `frontend/src/features/map/CityMap.tsx`
- Create: `frontend/src/features/map/layers.ts`
- Create: `frontend/src/features/map/map-style.ts`
- Create: `frontend/src/features/map/legend.tsx`
- Create: `frontend/src/features/map/CityMap.test.tsx`
- Create: `frontend/public/map/.gitkeep`

**Interfaces:** Consume bootstrap boundaries/graph/camera positions and current frames; render local base, H3 density, directional edge flow, ambulances, calls, and scenario regions.

- [ ] Write a failing layer-builder test asserting stable layer IDs, policy-specific ambulance color, selected-cell picking data, and empty-data safety.
- [ ] Implement pure `buildCityLayers(viewModel)` functions before mounting MapLibre/deck.gl.
- [ ] Register PMTiles protocol and a local style with a São Paulo initial viewport; surface a visible asset error if local map files are absent.
- [ ] Add accessible legend/toggles for density, flow, cameras, ambulances, calls, and event impact.
- [ ] Test layer toggling and cell/call/ambulance selection without a WebGL requirement.
- [ ] Run tests/typecheck and manually verify the real local São Paulo asset at desktop resolution.
- [ ] Commit: `feat: render offline São Paulo operations map`

## Task 3: Build Scenario and Fleet Controls

**Files:**
- Create: `frontend/src/features/scenarios/ScenarioPanel.tsx`
- Create: `frontend/src/features/scenarios/ScenarioCard.tsx`
- Create: `frontend/src/features/scenarios/SensorComposer.tsx`
- Create: `frontend/src/features/scenarios/ScenarioPanel.test.tsx`
- Create: `frontend/src/features/simulation/FleetControl.tsx`

**Interfaces:** Produce selected scenario ID and `SimulationRequest`; show built-in flood, event, and blocked-road cards plus deterministic typed observation parsing.

- [ ] Write failing interaction tests for selecting one card, showing affected time/location/impact, typing a sensor message, handling parser error, and changing fleet size.
- [ ] Implement scenario cards with clear simulated-source/confidence labels and active/queued visual states.
- [ ] Implement a debounced fleet slider with numeric value and accessible keyboard controls; send only on Run, not every drag event.
- [ ] Implement Sensor Composer through `transport.parseScenarioCard`; never imply it is live internet monitoring.
- [ ] Run tests and verify controls at 1280×720 without overlap.
- [ ] Commit: `feat: add simulated sensor and fleet controls`

## Task 4: Implement Streaming Playback State

**Files:**
- Create: `frontend/src/features/simulation/state.ts`
- Create: `frontend/src/features/simulation/useSimulation.ts`
- Create: `frontend/src/features/simulation/PlaybackControls.tsx`
- Create: `frontend/src/features/simulation/state.test.ts`
- Create: `frontend/src/features/simulation/PlaybackControls.test.tsx`

**Interfaces:** Consume validated frames from mock or WebSocket transport; expose baseline/optimized current frames, timeline, speed, connection/job state, and terminal metrics.

- [ ] Write reducer tests for out-of-order policy frames, duplicate replay frames, disconnect/reconnect, terminal state, reset, play/pause, scrub, and speed changes.
- [ ] Implement normalized frame storage keyed by `(policy, minute)` and deterministic current-frame selection.
- [ ] Implement `useSimulation` with create → status/subscribe → retry/replay; show failures and preserve received frames.
- [ ] Build controls for Run, reset, play/pause, 1×/2×/4×, and six-hour scrubber; announce current simulated time accessibly.
- [ ] Run tests and play the complete mock JSONL stream in approximately 60 seconds at default speed.
- [ ] Commit: `feat: stream and control paired simulation playback`

## Task 5: Present Before/After p90 and Operational Context

**Files:**
- Create: `frontend/src/features/metrics/ComparisonPanel.tsx`
- Create: `frontend/src/features/metrics/MetricCard.tsx`
- Create: `frontend/src/features/metrics/EquityPanel.tsx`
- Create: `frontend/src/features/metrics/ComparisonPanel.test.tsx`
- Create: `frontend/src/components/AppShell.tsx`

**Interfaces:** Consume both policy metrics; foreground p90 delta and percentage, with mean/p50/p95/service levels/equity/reposition as secondary evidence.

- [ ] Write exact formatting tests for `baseline p90=1260s`, `optimized p90=840s`: show `21.0 min`, `14.0 min`, `−7.0 min`, and `33.3% faster`.
- [ ] Test pending/partial/equal/worse outcomes honestly; improvements are green only when numerically positive.
- [ ] Build persistent Before/After cards, confidence/source note, service-level chips, worst-district p90, and reposition cost.
- [ ] Compose the responsive shell: map dominant, controls/scenarios left, comparison right, timeline bottom.
- [ ] Add a concise explainer linking Camera counts → Graph flow → H3 density → Call forecast → Allocation.
- [ ] Run tests and verify visual hierarchy at desktop and tablet widths.
- [ ] Commit: `feat: explain p90 response improvement`

## Task 6: Integrate the Local API and Verify the Demo

**Files:**
- Modify: `frontend/src/lib/api/http-transport.ts`
- Create: `frontend/tests/e2e/vertical-slice.spec.ts`
- Create: `frontend/tests/e2e/offline-demo.spec.ts`
- Create: `frontend/playwright.config.ts`

- [ ] Write an E2E test that selects Flood, sets fleet `120`, runs seed `42`, and waits for frames from both policies.
- [ ] Assert the map time advances, active scenario appears, optimized ambulances reposition, and Before/After p90 cards show terminal values.
- [ ] Add a WebSocket reconnect test using frame replay and ensure no duplicate timeline positions.
- [ ] Block all non-localhost requests in Playwright; assert the full demo emits zero external requests.
- [ ] Run `npm test`, typecheck, lint, production build, and both E2E specs against B's API.
- [ ] Run `rg -n "TODO|FIXME|placeholder|https?://" frontend/src frontend/public`; resolve incomplete or runtime-online hits.
- [ ] Publish build command, environment variables, screenshot, and E2E summary to the integrator.
- [ ] Commit: `test: verify offline City OS command portal`
