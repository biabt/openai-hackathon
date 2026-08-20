import { assertContract } from "@/lib/contracts/validate";
import type {
  BootstrapResponse,
  ScenarioObservation,
  SimulationCreatedResponse,
  SimulationFrame,
  SimulationRequest,
  SimulationJobResponse,
} from "@/lib/contracts/generated";
import {
  CityOsTransportError,
  type CityOsTransport,
  type CityMapData,
  type FrameListener,
  type FrameSubscriptionOptions,
  type TransportErrorListener,
  type Unsubscribe,
} from "./transport";

export interface HttpTransportOptions {
  baseUrl?: string;
  fetch?: typeof fetch;
  webSocket?: typeof WebSocket;
  reconnectDelayMs?: number;
  maxReconnectDelayMs?: number;
}

export class HttpCityOsTransport implements CityOsTransport {
  readonly #baseUrl: string;
  readonly #fetch: typeof fetch;
  readonly #WebSocket: typeof WebSocket;
  readonly #reconnectDelayMs: number;
  readonly #maxReconnectDelayMs: number;

  constructor(options: HttpTransportOptions = {}) {
    this.#baseUrl = (options.baseUrl ?? process.env.NEXT_PUBLIC_CITY_OS_API_URL ?? "").replace(/\/$/u, "");
    this.#fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
    this.#WebSocket = options.webSocket ?? globalThis.WebSocket;
    this.#reconnectDelayMs = options.reconnectDelayMs ?? 250;
    this.#maxReconnectDelayMs = options.maxReconnectDelayMs ?? 4_000;
  }

  async bootstrap(): Promise<BootstrapResponse> {
    return assertContract("BootstrapResponse", await this.#request("/api/bootstrap"));
  }

  async loadMapData(layerUrls: Record<string, string>): Promise<CityMapData> {
    const load = async <T>(key: string): Promise<T[]> => {
      const url = layerUrls[key];
      if (!url) return [];
      const value = await this.#request(url);
      if (!isLayerEnvelope(value)) {
        throw new CityOsTransportError(`City OS layer ${key} returned an invalid envelope.`);
      }
      return value.data as T[];
    };
    const [nodes, edges, h3Cells, cameraObservations, edgeStates, densities, demandPoints] = await Promise.all([
      load<CityMapData["nodes"][number]>("nodes"),
      load<CityMapData["edges"][number]>("edges"),
      load<CityMapData["h3Cells"][number]>("h3_cells"),
      load<CityMapData["cameraObservations"][number]>("camera_observations"),
      load<CityMapData["edgeStates"][number]>("edge_states"),
      load<CityMapData["densities"][number]>("h3_density"),
      load<CityMapData["demandPoints"][number]>("demand_points"),
    ]);
    return { nodes, edges, h3Cells, cameraObservations, edgeStates, densities, demandPoints };
  }

  async parseScenarioCard(text: string): Promise<ScenarioObservation> {
    const response = assertContract("ScenarioParseResponse", await this.#request("/api/scenario-cards/parse", {
      method: "POST", body: JSON.stringify({ text }),
    }));
    return response.observation;
  }

  async createSimulation(request: SimulationRequest): Promise<SimulationCreatedResponse> {
    const body = assertContract("SimulationRequest", request);
    return assertContract("SimulationCreatedResponse", await this.#request("/api/simulations", {
      method: "POST", body: JSON.stringify(body),
    }));
  }

  async getSimulation(id: string): Promise<SimulationJobResponse> {
    return assertContract("SimulationJobResponse", await this.#request(`/api/simulations/${encodeURIComponent(id)}`));
  }

  subscribeFrames(
    id: string,
    onFrame: FrameListener,
    onError?: TransportErrorListener,
    options: FrameSubscriptionOptions = {},
  ): Unsubscribe {
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;
    let reconnectAttempt = 0;
    const delivered = new Set<string>();
    const lastMinute: Record<SimulationFrame["policy"], number> = {
      baseline: options.afterMinute ?? -1,
      optimized: options.afterMinute ?? -1,
    };

    const report = (error: unknown) => onError?.(error instanceof Error ? error : new CityOsTransportError(String(error)));
    const replayMinute = () => {
      const observed = Object.values(lastMinute).filter((minute) => minute >= 0);
      return observed.length === 0 ? -1 : Math.max(0, Math.min(...observed) - 5);
    };
    const connect = () => {
      if (stopped || options.signal?.aborted) return;
      try { socket = new this.#WebSocket(this.#streamUrl(id, replayMinute())); }
      catch (error) { report(error); scheduleReconnect(); return; }

      socket.addEventListener("open", () => { reconnectAttempt = 0; });
      socket.addEventListener("message", (event) => {
        void decodeMessage(event.data).then((value) => {
          const frame = assertContract("SimulationFrame", value);
          const key = `${frame.policy}:${frame.minute}`;
          if (delivered.has(key)) return;
          delivered.add(key);
          lastMinute[frame.policy] = Math.max(lastMinute[frame.policy], frame.minute);
          onFrame(frame);
        }).catch(report);
      });
      socket.addEventListener("error", () => report(new CityOsTransportError("Simulation stream connection failed.")));
      socket.addEventListener("close", (event) => {
        socket = null;
        if (!stopped && !options.signal?.aborted && event.code !== 1000) scheduleReconnect();
      });
    };

    const scheduleReconnect = () => {
      if (stopped || options.reconnect === false || reconnectTimer) return;
      const delay = Math.min(this.#reconnectDelayMs * 2 ** reconnectAttempt, this.#maxReconnectDelayMs);
      reconnectAttempt += 1;
      reconnectTimer = setTimeout(() => { reconnectTimer = null; connect(); }, delay);
    };

    const unsubscribe = () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      reconnectTimer = null;
      socket?.close(1000, "Client unsubscribed");
      socket = null;
    };
    options.signal?.addEventListener("abort", unsubscribe, { once: true });
    connect();
    return unsubscribe;
  }

  async #request(path: string, init: RequestInit = {}): Promise<unknown> {
    let response: Response;
    try {
      response = await this.#fetch(`${this.#baseUrl}${path}`, {
        ...init,
        headers: { Accept: "application/json", ...(init.body ? { "Content-Type": "application/json" } : {}), ...init.headers },
      });
    } catch (error) {
      throw new CityOsTransportError(`City OS API is unavailable at ${path}.`, { cause: error });
    }
    if (!response.ok) throw new CityOsTransportError(`City OS API request failed (${response.status}) at ${path}.`, { status: response.status });
    try { return await response.json(); }
    catch (error) { throw new CityOsTransportError(`City OS API returned invalid JSON at ${path}.`, { status: response.status, cause: error }); }
  }

  #streamUrl(id: string, afterMinute: number): string {
    const origin = typeof window === "undefined" ? "http://localhost" : window.location.href;
    const base = new URL(this.#baseUrl || "/", origin);
    base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
    base.pathname = `/api/simulations/${encodeURIComponent(id)}/stream`;
    base.search = "";
    if (afterMinute >= 0) base.searchParams.set("after_minute", String(afterMinute));
    return base.toString();
  }
}

function isLayerEnvelope(value: unknown): value is { schema_version: "1.0"; data: unknown[] } {
  return typeof value === "object" && value !== null
    && (value as { schema_version?: unknown }).schema_version === "1.0"
    && Array.isArray((value as { data?: unknown }).data);
}

async function decodeMessage(data: unknown): Promise<unknown> {
  if (typeof data === "string") return JSON.parse(data);
  if (data instanceof Blob) return JSON.parse(await data.text());
  if (data instanceof ArrayBuffer) return JSON.parse(new TextDecoder().decode(data));
  throw new CityOsTransportError("Simulation stream sent an unsupported message type.");
}
