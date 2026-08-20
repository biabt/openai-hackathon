import type {
  BootstrapResponse,
  ScenarioObservation,
  SimulationCreatedResponse,
  SimulationFrame,
  SimulationRequest,
  SimulationJobResponse,
  RoadEdge,
  RoadNode,
} from "@/lib/contracts/generated";

export type H3CellLayerRow = { cell: string; geometry: unknown };
export type CameraObservationLayerRow = {
  camera_id: string;
  edge_id: number;
  bucket_start: string;
  object_class: string;
  direction: string;
  count: number;
  confidence: number;
};
export type EdgeStateLayerRow = {
  edge_id: number;
  bucket_start: string;
  flow_vph: number;
  speed_kph: number;
  travel_seconds: number;
  occupancy_people: number;
  confidence: number;
};
export type H3DensityLayerRow = {
  cell: string;
  bucket_start: string;
  density_people_km2: number;
  emergency_intensity_hour: number;
  confidence: number;
};
export type DemandPointLayerRow = {
  id: string;
  node_id: number;
  h3_cell: string;
  longitude: number;
  latitude: number;
  historical_occurrences: number;
  injured: number;
  fatalities: number;
  weight: number;
};
export type CityMapData = {
  nodes: RoadNode[];
  edges: RoadEdge[];
  h3Cells: H3CellLayerRow[];
  cameraObservations: CameraObservationLayerRow[];
  edgeStates: EdgeStateLayerRow[];
  densities: H3DensityLayerRow[];
  demandPoints: DemandPointLayerRow[];
};

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
  loadMapData(layerUrls: Record<string, string>): Promise<CityMapData>;
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
