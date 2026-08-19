import { describe, expect, it } from "vitest";

import type { SimulationFrame, SimulationMetrics } from "../../lib/contracts/generated";
import {
  createInitialSimulationState,
  selectCurrentFrames,
  selectTerminalMetrics,
  simulationReducer,
} from "./state";

function metrics(policy: "baseline" | "optimized", p90: number): SimulationMetrics {
  return {
    policy,
    mean_seconds: p90 * 0.7,
    p50_seconds: p90 * 0.6,
    p90_seconds: p90,
    p95_seconds: p90 * 1.1,
    within_8m_pct: 40,
    within_12m_pct: 60,
    within_20m_pct: 80,
    worst_district_p90_seconds: p90 * 1.2,
    queued_calls: 0,
    unserved_calls: 0,
    reposition_km: 10,
  };
}

function frame(
  policy: "baseline" | "optimized",
  minute: number,
  p90 = 900,
): SimulationFrame {
  return {
    minute,
    policy,
    ambulances: [],
    calls: [],
    metrics: metrics(policy, p90),
    active_scenario_ids: [],
  };
}

describe("simulationReducer", () => {
  it("normalizes out-of-order policy frames and selects the latest frame at or before time", () => {
    let state = createInitialSimulationState();
    state = simulationReducer(state, { type: "frameReceived", frame: frame("optimized", 10) });
    state = simulationReducer(state, { type: "frameReceived", frame: frame("baseline", 5) });
    state = simulationReducer(state, { type: "frameReceived", frame: frame("baseline", 10) });
    state = simulationReducer(state, { type: "scrub", minute: 7 });

    expect(state.timeline).toEqual([5, 10]);
    expect(selectCurrentFrames(state)).toEqual({
      baseline: frame("baseline", 5),
      optimized: null,
    });
  });

  it("keeps duplicate replay frames idempotent", () => {
    const replayed = frame("baseline", 15, 1_260);
    let state = simulationReducer(createInitialSimulationState(), {
      type: "frameReceived",
      frame: replayed,
    });
    state = simulationReducer(state, { type: "frameReceived", frame: replayed });

    expect(state.timeline).toEqual([15]);
    expect(Object.keys(state.frames.baseline)).toHaveLength(1);
    expect(state.frames.baseline[15]).toBe(replayed);
  });

  it("preserves frames through disconnect and reconnect", () => {
    let state = simulationReducer(createInitialSimulationState(), {
      type: "frameReceived",
      frame: frame("optimized", 20),
    });
    state = simulationReducer(state, {
      type: "connectionChanged",
      connection: "disconnected",
    });
    state = simulationReducer(state, {
      type: "connectionChanged",
      connection: "connected",
    });

    expect(state.connection).toBe("connected");
    expect(state.frames.optimized[20]).toBeDefined();
  });

  it("exposes terminal metrics without interrupting a running playback", () => {
    let state = createInitialSimulationState();
    state = simulationReducer(state, { type: "frameReceived", frame: frame("baseline", 360, 1_260) });
    state = simulationReducer(state, { type: "frameReceived", frame: frame("optimized", 360, 840) });
    state = simulationReducer(state, { type: "play" });
    state = simulationReducer(state, { type: "jobChanged", job: "completed" });

    expect(state.playing).toBe(true);
    expect(state.job).toBe("completed");
    expect(state.connection).toBe("disconnected");
    expect(selectTerminalMetrics(state).baseline?.p90_seconds).toBe(1_260);
    expect(selectTerminalMetrics(state).optimized?.p90_seconds).toBe(840);
  });

  it("supports play, pause, scrub, speed, ticking and reset", () => {
    let state = createInitialSimulationState();
    state = simulationReducer(state, { type: "play" });
    state = simulationReducer(state, { type: "setSpeed", speed: 4 });
    state = simulationReducer(state, { type: "tick", elapsedSeconds: 1 });
    expect(state.currentMinute).toBe(24);
    state = simulationReducer(state, { type: "pause" });
    state = simulationReducer(state, { type: "scrub", minute: 400 });
    expect(state.currentMinute).toBe(360);
    state = simulationReducer(state, { type: "reset" });
    expect(state).toEqual(createInitialSimulationState());
  });
});
