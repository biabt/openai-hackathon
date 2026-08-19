import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CityOsTransport } from "../../lib/api/transport";
import type {
  SimulationFrame,
  SimulationRequest,
  SimulationJobResponse,
} from "../../lib/contracts/generated";
import { useSimulation } from "./useSimulation";

const request: SimulationRequest = { scenario_id: "flood", fleet_size: 120, seed: 42 };

function frame(policy: "baseline" | "optimized", minute: number): SimulationFrame {
  return {
    minute,
    policy,
    ambulances: [],
    calls: [],
    active_scenario_ids: ["flood"],
    metrics: {
      policy,
      mean_seconds: 700,
      p50_seconds: 600,
      p90_seconds: policy === "baseline" ? 1_260 : 840,
      p95_seconds: 1_500,
      within_8m_pct: 40,
      within_12m_pct: 60,
      within_20m_pct: 80,
      worst_district_p90_seconds: 1_600,
      queued_calls: 0,
      unserved_calls: 0,
      reposition_km: 10,
    },
  };
}

function runningStatus(): SimulationJobResponse {
  return { simulation_id: "sim-42", status: "running", request, metrics: null, methodology: null, error: null };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("useSimulation", () => {
  it("creates, polls, subscribes and stores paired frames", async () => {
    let receive: ((value: SimulationFrame) => void) | undefined;
    const unsubscribe = vi.fn();
    const transport = {
      createSimulation: vi.fn().mockResolvedValue({ simulation_id: "sim-42", status: "queued" }),
      getSimulation: vi.fn().mockResolvedValue(runningStatus()),
      subscribeFrames: vi.fn(
        (_id: string, onFrame: (value: SimulationFrame) => void) => {
          receive = onFrame;
          return unsubscribe;
        },
      ),
    } as unknown as CityOsTransport;

    const { result, unmount } = renderHook(() =>
      useSimulation(transport, { statusPollMs: 10_000 }),
    );

    await act(async () => {
      await result.current.run(request);
    });
    act(() => {
      receive?.(frame("optimized", 5));
      receive?.(frame("baseline", 5));
    });

    expect(transport.createSimulation).toHaveBeenCalledWith(request);
    expect(transport.getSimulation).toHaveBeenCalledWith("sim-42");
    expect(transport.subscribeFrames).toHaveBeenCalledWith(
      "sim-42",
      expect.any(Function),
      expect.any(Function),
      expect.objectContaining({ reconnect: false }),
    );
    expect(result.current.state.timeline).toEqual([5]);
    expect(result.current.state.frames.baseline[5]?.metrics.p90_seconds).toBe(1_260);
    expect(result.current.state.frames.optimized[5]?.metrics.p90_seconds).toBe(840);

    unmount();
    expect(unsubscribe).toHaveBeenCalled();
  });

  it("retries with one replay bucket while preserving validated frames", async () => {
    vi.useFakeTimers();
    const errors: Array<(error: unknown) => void> = [];
    const receives: Array<(value: SimulationFrame) => void> = [];
    const transport = {
      createSimulation: vi.fn().mockResolvedValue({ simulation_id: "sim-42", status: "queued" }),
      getSimulation: vi.fn().mockResolvedValue(runningStatus()),
      subscribeFrames: vi.fn(
        (
          _id: string,
          onFrame: (value: SimulationFrame) => void,
          onError: (error: unknown) => void,
        ) => {
          receives.push(onFrame);
          errors.push(onError);
          return vi.fn();
        },
      ),
    } as unknown as CityOsTransport;

    const { result, unmount } = renderHook(() =>
      useSimulation(transport, { statusPollMs: 10_000 }),
    );
    await act(async () => {
      await result.current.run(request);
    });
    act(() => receives[0]?.(frame("baseline", 10)));
    act(() => errors[0]?.(new Error("conexão interrompida")));
    expect(result.current.state.connection).toBe("retrying");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });

    expect(transport.subscribeFrames).toHaveBeenCalledTimes(2);
    expect(transport.subscribeFrames).toHaveBeenLastCalledWith(
      "sim-42",
      expect.any(Function),
      expect.any(Function),
      expect.objectContaining({ afterMinute: 5 }),
    );
    expect(result.current.state.frames.baseline[10]).toBeDefined();
    unmount();
  });
});
