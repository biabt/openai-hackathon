import type {
  BootstrapResponse,
  ScenarioObservation,
  SimulationCreatedResponse,
  SimulationFrame,
  SimulationRequest,
  SimulationJobResponse,
} from "@/lib/contracts/generated";

export interface FrameSubscriptionOptions {
  /** Ask a replay-capable server to resume after this simulated minute. */
  afterMinute?: number;
  /** Ends the subscription without reporting a transport failure. */
  signal?: AbortSignal;
  /** Reconnect abnormal WebSocket closes. Defaults to true for HTTP transport. */
  reconnect?: boolean;
}

export type FrameListener = (frame: SimulationFrame) => void;
export type TransportErrorListener = (error: Error) => void;
export type Unsubscribe = () => void;

export interface CityOsTransport {
  bootstrap(): Promise<BootstrapResponse>;
  parseScenarioCard(text: string): Promise<ScenarioObservation>;
  createSimulation(request: SimulationRequest): Promise<SimulationCreatedResponse>;
  getSimulation(id: string): Promise<SimulationJobResponse>;
  subscribeFrames(
    id: string,
    onFrame: FrameListener,
    onError?: TransportErrorListener,
    options?: FrameSubscriptionOptions,
  ): Unsubscribe;
}

export class CityOsTransportError extends Error {
  readonly status: number | null;

  constructor(message: string, options: { status?: number; cause?: unknown } = {}) {
    super(message, { cause: options.cause });
    this.name = "CityOsTransportError";
    this.status = options.status ?? null;
  }
}
