import bootstrapFixture from "@/lib/contracts/fixtures/bootstrap.json";
import streamFixture from "@/lib/contracts/fixtures/stream.json";
import { assertContract } from "@/lib/contracts/validate";
import type {
  BootstrapResponse,
  ScenarioObservation,
  SimulationFrame,
  SimulationRequest,
  SimulationJobResponse,
} from "@/lib/contracts/generated";
import {
  CityOsTransportError,
  type CityMapData,
  type CityOsTransport,
  type FrameListener,
  type FrameSubscriptionOptions,
  type TransportErrorListener,
  type Unsubscribe,
} from "./transport";

export interface MockTransportOptions {
  bootstrap?: unknown;
  frames?: readonly unknown[];
  frameIntervalMs?: number;
  defaultFleetSize?: number;
}

export class MockCityOsTransport implements CityOsTransport {
  readonly #bootstrap: BootstrapResponse;
  readonly #frames: readonly SimulationFrame[];
  readonly #frameIntervalMs: number;
  #request: SimulationRequest | null = null;
  #deliveredFrames = 0;

  constructor(options: MockTransportOptions = {}) {
    const bootstrap = structuredClone(options.bootstrap ?? bootstrapFixture) as BootstrapResponse;
    if (options.defaultFleetSize !== undefined) {
      bootstrap.fleet_size_bounds.default = options.defaultFleetSize;
    }
    this.#bootstrap = assertContract("BootstrapResponse", bootstrap);
    this.#frames = (options.frames ?? streamFixture).map((frame) => assertContract("SimulationFrame", frame));
    this.#frameIntervalMs = options.frameIntervalMs ?? 0;
  }

  async bootstrap(): Promise<BootstrapResponse> {
    return structuredClone(this.#bootstrap);
  }

  async loadMapData(): Promise<CityMapData> {
    return {
      nodes: [], edges: [], h3Cells: [], cameraObservations: [],
      edgeStates: [], densities: [], demandPoints: [],
    };
  }

  async parseScenarioCard(text: string): Promise<ScenarioObservation> {
    const normalized = text.trim().toLocaleLowerCase("pt-BR");
    if (!normalized) throw new CityOsTransportError("Scenario observation text cannot be empty.");
    const scenario = this.#bootstrap.scenarios.find((item) =>
      normalized.includes(item.type.replace("_", " ")) || normalized.includes(item.id.split("-")[0] ?? ""),
    );
    if (!scenario) throw new CityOsTransportError("The simulated observation did not match a bundled scenario card.");
    return structuredClone(scenario);
  }

  async createSimulation(request: SimulationRequest) {
    this.#request = structuredClone(assertContract("SimulationRequest", request));
    this.#deliveredFrames = 0;
    return assertContract("SimulationCreatedResponse", { simulation_id: `sim-${request.seed}`, status: "queued" });
  }

  async getSimulation(id: string): Promise<SimulationJobResponse> {
    if (!this.#request) throw new CityOsTransportError(`Simulation ${id} was not created.`, { status: 404 });
    const completed = this.#frames.length > 0 && this.#deliveredFrames >= this.#frames.length;
    const terminalFrames = completed ? this.#frames.slice().reverse() : [];
    const baseline = terminalFrames.find((frame) => frame.policy === "baseline")?.metrics;
    const optimized = terminalFrames.find((frame) => frame.policy === "optimized")?.metrics;
    return assertContract("SimulationJobResponse", {
      simulation_id: id,
      status: completed ? "completed" : "running",
      request: this.#request,
      metrics: baseline && optimized ? { baseline, optimized } : null,
      methodology: baseline && optimized ? {
        call_tape_seed: this.#request.seed,
        calibration_target_seconds: 1260,
        calibration_description: "Bundled deterministic mock transport",
        data_label: "simulated",
      } : null,
      error: null,
    });
  }

  subscribeFrames(
    _id: string,
    onFrame: FrameListener,
    onError?: TransportErrorListener,
    options: FrameSubscriptionOptions = {},
  ): Unsubscribe {
    let stopped = false;
    const timers = new Set<ReturnType<typeof setTimeout>>();
    const frames = this.#frames.filter((frame) => frame.minute > (options.afterMinute ?? -1));

    frames.forEach((frame, index) => {
      const timer = setTimeout(() => {
        timers.delete(timer);
        if (stopped || options.signal?.aborted) return;
        try {
          const videoFrame = structuredClone(frame);
          if (this.#request && videoFrame.minute >= 5) {
            videoFrame.active_scenario_ids = [this.#request.scenario_id];
          }
          onFrame(assertContract("SimulationFrame", videoFrame));
          this.#deliveredFrames += 1;
        } catch (error) {
          onError?.(toError(error));
        }
      }, this.#frameIntervalMs * index);
      timers.add(timer);
    });

    const unsubscribe = () => {
      stopped = true;
      timers.forEach(clearTimeout);
      timers.clear();
    };
    options.signal?.addEventListener("abort", unsubscribe, { once: true });
    return unsubscribe;
  }
}

function toError(value: unknown): Error {
  return value instanceof Error ? value : new Error(String(value));
}
