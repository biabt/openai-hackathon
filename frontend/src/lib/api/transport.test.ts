import bootstrapFixture from "@/lib/contracts/fixtures/bootstrap.json";
import streamFixture from "@/lib/contracts/fixtures/stream.json";
import { ContractValidationError, assertContract } from "@/lib/contracts/validate";
import type { SimulationFrame, SimulationRequest } from "@/lib/contracts/generated";
import { HttpCityOsTransport } from "./http-transport";
import { MockCityOsTransport } from "./mock-transport";

describe("frozen contract fixtures", () => {
  it("validates the bootstrap and every JSONL-derived stream frame", () => {
    expect(assertContract("BootstrapResponse", bootstrapFixture)).toMatchObject({
      city: "São Paulo",
      simulation_duration_minutes: 360,
      frame_interval_minutes: 5,
    });
    expect(streamFixture).toHaveLength(6);
    expect(streamFixture.map((frame) => assertContract("SimulationFrame", frame))).toHaveLength(6);
  });

  it("rejects an unknown ambulance status at the runtime boundary", () => {
    const invalid = structuredClone(streamFixture[0]) as unknown as SimulationFrame;
    Object.assign(invalid.ambulances[0]!, { status: "FLYING" });
    expect(() => assertContract("SimulationFrame", invalid)).toThrow(ContractValidationError);
  });
});

describe("transport parity", () => {
  beforeEach(() => FakeWebSocket.reset());

  it("returns the same validated bootstrap, scenario, job and status messages", async () => {
    const flood = bootstrapFixture.scenarios[0]!;
    const request: SimulationRequest = { scenario_id: flood.id, fleet_size: 120, seed: 42 };
    const runningStatus = {
      simulation_id: "sim-42",
      status: "running",
      request,
      metrics: null,
      methodology: null,
      error: null,
    };
    const fetchStub = responseQueue([
      bootstrapFixture,
      { observation: flood, used_fallback: false, error: null },
      { simulation_id: "sim-42", status: "queued" },
      runningStatus,
    ]);
    const http = new HttpCityOsTransport({ baseUrl: "http://127.0.0.1:8000", fetch: fetchStub });
    const mock = new MockCityOsTransport({ frames: [streamFixture[0]!] });

    await expect(http.bootstrap()).resolves.toEqual(await mock.bootstrap());
    await expect(http.parseScenarioCard("flood")).resolves.toEqual(await mock.parseScenarioCard("flood"));
    await expect(http.createSimulation(request)).resolves.toEqual(await mock.createSimulation(request));
    await expect(http.getSimulation("sim-42")).resolves.toEqual(await mock.getSimulation("sim-42"));
  });

  it("delivers identical validated domain frames from timers and WebSocket", async () => {
    const expected = assertContract("SimulationFrame", streamFixture[0]);
    const mock = new MockCityOsTransport({ frames: [expected], frameIntervalMs: 0 });
    const http = new HttpCityOsTransport({
      baseUrl: "http://127.0.0.1:8000",
      fetch: vi.fn() as unknown as typeof fetch,
      webSocket: FakeWebSocket as unknown as typeof WebSocket,
    });

    const mockFrame = new Promise<SimulationFrame>((resolve, reject) => mock.subscribeFrames("job", resolve, reject));
    const httpFrame = new Promise<SimulationFrame>((resolve, reject) => http.subscribeFrames("job", resolve, reject));
    FakeWebSocket.latest?.emit("message", { data: JSON.stringify(expected) });

    await expect(httpFrame).resolves.toEqual(await mockFrame);
  });

  it("deduplicates replayed policy/minute frames after reconnect", async () => {
    vi.useFakeTimers();
    const received: SimulationFrame[] = [];
    const transport = new HttpCityOsTransport({
      baseUrl: "http://127.0.0.1:8000",
      fetch: vi.fn() as unknown as typeof fetch,
      webSocket: FakeWebSocket as unknown as typeof WebSocket,
      reconnectDelayMs: 10,
    });
    const stop = transport.subscribeFrames("job", (frame) => received.push(frame));
    const firstSocket = FakeWebSocket.latest!;
    firstSocket.emit("message", { data: JSON.stringify(streamFixture[0]) });
    await Promise.resolve();
    firstSocket.emit("close", { code: 1006 });
    await vi.advanceTimersByTimeAsync(10);
    const replaySocket = FakeWebSocket.latest!;
    replaySocket.emit("message", { data: JSON.stringify(streamFixture[0]) });
    replaySocket.emit("message", { data: JSON.stringify(streamFixture[2]) });
    await Promise.resolve();

    expect(received.map(({ policy, minute }) => `${policy}:${minute}`)).toEqual(["baseline:0", "baseline:5"]);
    expect(replaySocket.url).toContain("after_minute=0");
    stop();
    vi.useRealTimers();
  });
});

function responseQueue(values: readonly unknown[]): typeof fetch {
  const queue = [...values];
  return vi.fn(async () => {
    const value = queue.shift();
    return { ok: true, status: 200, json: async () => structuredClone(value) } as Response;
  }) as unknown as typeof fetch;
}

type Listener = (event: never) => void;

class FakeWebSocket {
  static latest: FakeWebSocket | undefined;
  readonly url: string;
  readonly #listeners = new Map<string, Set<Listener>>();

  constructor(url: string | URL) {
    this.url = String(url);
    FakeWebSocket.latest = this;
    queueMicrotask(() => this.emit("open", {}));
  }

  static reset() { FakeWebSocket.latest = undefined; }

  addEventListener(type: string, listener: Listener) {
    const listeners = this.#listeners.get(type) ?? new Set<Listener>();
    listeners.add(listener);
    this.#listeners.set(type, listeners);
  }

  emit(type: string, event: object) {
    this.#listeners.get(type)?.forEach((listener) => listener(event as never));
  }

  close(code = 1000) { this.emit("close", { code }); }
}
