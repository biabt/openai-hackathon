import { PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import type { Layer, PickingInfo } from "@deck.gl/core";
import type { BootstrapResponse, SimulationFrame } from "@/lib/contracts/generated";
import type { CityMapData } from "@/lib/api/transport";
import {
  MOCK_AMBULANCES,
  MOCK_CAMERAS,
  MOCK_DEMAND_NODES,
  MOCK_DENSITY,
  MOCK_FLOW_EDGES,
  MOCK_NODE_POSITIONS,
} from "./map-fixture";

export type LongitudeLatitude = readonly [longitude: number, latitude: number];

export type MapSelection = {
  kind: "cell" | "flow" | "camera" | "ambulance" | "call" | "impact";
  id: string;
  datum: unknown;
};

export type CityLayerVisibility = {
  density: boolean;
  flow: boolean;
  cameras: boolean;
  ambulances: boolean;
  calls: boolean;
  impact: boolean;
};

export const DEFAULT_CITY_LAYER_VISIBILITY: CityLayerVisibility = {
  density: true,
  flow: true,
  cameras: true,
  ambulances: true,
  calls: true,
  impact: true,
};

export type DensityCell = {
  h3_index: string;
  density: number;
  confidence?: number;
};

export type FlowEdge = {
  id: string | number;
  path: LongitudeLatitude[];
  flow: number;
  confidence?: number;
};

export type MapCamera = {
  id: string;
  position: LongitudeLatitude;
  confidence?: number;
};

export type MapAmbulance = {
  id: string;
  position: LongitudeLatitude;
  policy?: "baseline" | "optimized";
  status?: string;
};

export type MapCall = {
  id: string;
  position: LongitudeLatitude;
  status?: string;
  priority?: string | number;
};

export type ScenarioImpact = {
  id: string;
  h3Index: string;
  type?: string;
};

export type CityMapViewModel = {
  policy?: "baseline" | "optimized";
  densityCells?: readonly DensityCell[];
  flowEdges?: readonly FlowEdge[];
  cameras?: readonly MapCamera[];
  ambulances?: readonly MapAmbulance[];
  calls?: readonly MapCall[];
  scenarioImpacts?: readonly ScenarioImpact[];
  visibility?: Partial<CityLayerVisibility>;
  onSelect?: (selection: MapSelection) => void;
};

export type CityMapViewModelOptions = {
  /** API mode never fills a missing operational layer with local fixtures. */
  source?: "api" | "fixture";
};

const clamp = (value: number, minimum = 0, maximum = 1) =>
  Math.max(minimum, Math.min(maximum, Number.isFinite(value) ? value : minimum));

const densityColor = (density: number, confidence = 1): [number, number, number, number] => {
  const intensity = clamp(density / 100);
  return [255, Math.round(198 - intensity * 125), 73, Math.round(45 + clamp(confidence) * 150)];
};

const ambulanceColor = (policy: "baseline" | "optimized"):
  [number, number, number, number] =>
  policy === "optimized" ? [45, 212, 191, 255] : [251, 146, 60, 255];

function selectionHandler(
  kind: MapSelection["kind"],
  id: (datum: never) => string,
  onSelect?: CityMapViewModel["onSelect"],
) {
  return (info: PickingInfo) => {
    if (!info.object || !onSelect) return;
    onSelect({ kind, id: id(info.object as never), datum: info.object });
  };
}

/** Pure layer factory. It is deliberately independent from MapLibre and WebGL. */
export function buildCityLayers(viewModel: CityMapViewModel): Layer[] {
  const visibility = { ...DEFAULT_CITY_LAYER_VISIBILITY, ...viewModel.visibility };
  const policy = viewModel.policy ?? "optimized";

  return [
    new H3HexagonLayer<DensityCell>({
      id: "city-density",
      data: [...(viewModel.densityCells ?? [])],
      visible: visibility.density,
      pickable: true,
      filled: true,
      extruded: false,
      getHexagon: (cell) => cell.h3_index,
      getFillColor: (cell) => densityColor(cell.density, cell.confidence),
      onClick: selectionHandler("cell", (cell: DensityCell) => cell.h3_index, viewModel.onSelect),
      updateTriggers: { getFillColor: [policy] },
    }),
    new PathLayer<FlowEdge>({
      id: "city-directional-flow",
      data: [...(viewModel.flowEdges ?? [])],
      visible: visibility.flow,
      pickable: true,
      widthUnits: "pixels",
      widthMinPixels: 1,
      getPath: (edge) => edge.path as [number, number][],
      getWidth: (edge) => 1 + clamp(edge.flow / 1200) * 5,
      getColor: (edge) => [56, 189, 248, Math.round(55 + clamp(edge.confidence ?? 0.5) * 180)],
      onClick: selectionHandler("flow", (edge: FlowEdge) => String(edge.id), viewModel.onSelect),
    }),
    new ScatterplotLayer<MapCamera>({
      id: "city-cameras",
      data: [...(viewModel.cameras ?? [])],
      visible: visibility.cameras,
      pickable: true,
      radiusUnits: "pixels",
      getRadius: 5,
      getPosition: (camera) => camera.position as [number, number],
      getFillColor: [216, 180, 254, 230],
      getLineColor: [255, 255, 255, 220],
      lineWidthMinPixels: 1,
      stroked: true,
      onClick: selectionHandler("camera", (camera: MapCamera) => camera.id, viewModel.onSelect),
    }),
    new ScatterplotLayer<MapCall>({
      id: "city-calls",
      data: [...(viewModel.calls ?? [])],
      visible: visibility.calls,
      pickable: true,
      radiusUnits: "pixels",
      getRadius: 9,
      getPosition: (call) => call.position as [number, number],
      filled: false,
      getLineColor: (call) => call.status === "QUEUED" ? [239, 68, 68, 255] : [250, 204, 21, 245],
      lineWidthMinPixels: 2,
      stroked: true,
      onClick: selectionHandler("call", (call: MapCall) => call.id, viewModel.onSelect),
    }),
    new ScatterplotLayer<MapAmbulance>({
      id: "city-ambulances",
      data: [...(viewModel.ambulances ?? [])],
      visible: visibility.ambulances,
      pickable: true,
      radiusUnits: "pixels",
      getRadius: 8,
      radiusMinPixels: 8,
      radiusMaxPixels: 14,
      getPosition: (ambulance) => ambulance.position as [number, number],
      getFillColor: (ambulance) => ambulanceColor(ambulance.policy ?? policy),
      getLineColor: [255, 255, 255, 255],
      lineWidthMinPixels: 2.5,
      stroked: true,
      onClick: selectionHandler("ambulance", (ambulance: MapAmbulance) => ambulance.id, viewModel.onSelect),
      updateTriggers: { getFillColor: [policy] },
    }),
    new H3HexagonLayer<ScenarioImpact>({
      id: "city-scenario-impact",
      data: [...(viewModel.scenarioImpacts ?? [])],
      visible: visibility.impact,
      pickable: true,
      filled: true,
      stroked: true,
      getHexagon: (impact) => impact.h3Index,
      getFillColor: [239, 68, 68, 55],
      getLineColor: [248, 113, 113, 230],
      getLineWidth: 2,
      lineWidthUnits: "pixels",
      onClick: selectionHandler("impact", (impact: ScenarioImpact) => impact.id, viewModel.onSelect),
    }),
  ];
}

/** Converts frozen bootstrap/frame contracts into the map's render-only model. */
export function createCityMapViewModel(
  bootstrap: BootstrapResponse,
  frame?: SimulationFrame | null,
  apiMapData?: CityMapData | null,
  options: CityMapViewModelOptions = {},
): CityMapViewModel {
  const source = options.source ?? (apiMapData ? "api" : "fixture");
  const scenarioImpacts = (frame?.active_scenario_ids ?? []).flatMap((scenarioId) => {
    const scenario = bootstrap.scenarios.find((item) => item.id === scenarioId);
    return (scenario?.affected_h3 ?? []).map((h3Index) => ({
      id: `${scenarioId}:${h3Index}`,
      h3Index,
      type: scenario?.type,
    }));
  });

  if (source === "api") {
    return createApiCityMapViewModel(frame, apiMapData, scenarioImpacts);
  }

  const operationalPositions = MOCK_AMBULANCES.map(({ position }) => position);
  const nodePosition = (nodeId: number) => MOCK_NODE_POSITIONS[nodeId];
  const ambulanceOccurrences = new Map<string, number>();
  const frameAmbulances = (frame?.ambulances ?? []).flatMap((ambulance, index) => {
    const position = nodePosition(ambulance.node_id)
      ?? operationalPositions[index % operationalPositions.length];
    if (!position) return [];
    const positionKey = `${position[0].toFixed(6)}:${position[1].toFixed(6)}`;
    const occurrence = ambulanceOccurrences.get(positionKey) ?? 0;
    ambulanceOccurrences.set(positionKey, occurrence + 1);
    return [{
      id: ambulance.id,
      position: spreadCoincidentPoint(position, occurrence),
      policy: frame?.policy,
      status: ambulance.status,
    }];
  });
  const frameCalls = (frame?.calls ?? []).flatMap((call, index) => {
    const position = nodePosition(call.node_id)
      ?? MOCK_DEMAND_NODES[index % MOCK_DEMAND_NODES.length]?.position;
    return position ? [{ id: call.id, position, status: call.status, priority: call.priority }] : [];
  });

  return {
    policy: frame?.policy,
    densityCells: MOCK_DENSITY,
    flowEdges: MOCK_FLOW_EDGES,
    cameras: MOCK_CAMERAS,
    ambulances: mergeMapPoints(frameAmbulances, MOCK_AMBULANCES, frame?.policy),
    calls: mergeMapPoints(frameCalls, MOCK_DEMAND_NODES),
    scenarioImpacts,
  };
}

function createApiCityMapViewModel(
  frame: SimulationFrame | null | undefined,
  apiMapData: CityMapData | null | undefined,
  scenarioImpacts: readonly ScenarioImpact[],
): CityMapViewModel {
  const nodePositions = new Map((apiMapData?.nodes ?? []).map(
    (node) => [node.node_id, [node.x, node.y] as LongitudeLatitude],
  ));
  const edges = new Map((apiMapData?.edges ?? []).map((edge) => [edge.edge_id, edge]));
  const demandByNode = new Map((apiMapData?.demandPoints ?? []).map(
    (point) => [point.node_id, [point.longitude, point.latitude] as LongitudeLatitude],
  ));
  const demandByCell = new Map((apiMapData?.demandPoints ?? []).map(
    (point) => [point.h3_cell, [point.longitude, point.latitude] as LongitudeLatitude],
  ));
  const edgePath = (edgeId: number): LongitudeLatitude[] | null => {
    const edge = edges.get(edgeId);
    if (!edge) return null;
    const start = nodePositions.get(edge.u);
    const end = nodePositions.get(edge.v);
    return start && end ? [start, end] : null;
  };

  const densityCells = latestBy(apiMapData?.densities ?? [], (row) => row.cell).map((row) => ({
    h3_index: row.cell,
    density: row.density_people_km2,
    confidence: row.confidence,
  }));
  const flowEdges = latestBy(apiMapData?.edgeStates ?? [], (row) => row.edge_id).flatMap((row) => {
    const path = edgePath(row.edge_id);
    return path ? [{ id: row.edge_id, path, flow: row.flow_vph, confidence: row.confidence }] : [];
  });
  const cameras = latestBy(apiMapData?.cameraObservations ?? [], (row) => row.camera_id).flatMap((row) => {
    const path = edgePath(row.edge_id);
    if (!path) return [];
    return [{
      id: row.camera_id,
      position: midpoint(path[0]!, path[path.length - 1]!),
      confidence: row.confidence,
    }];
  });
  const ambulances = (frame?.ambulances ?? []).flatMap((ambulance) => {
    const position = nodePositions.get(ambulance.node_id);
    return position ? [{
      id: ambulance.id,
      position,
      policy: frame?.policy,
      status: ambulance.status,
    }] : [];
  });
  const historicalDemand = (apiMapData?.demandPoints ?? []).map((point) => ({
    id: point.id,
    position: [point.longitude, point.latitude] as LongitudeLatitude,
    status: "HISTORICAL",
    priority: point.weight,
  }));
  const activeCalls = (frame?.calls ?? []).flatMap((call) => {
    const position = nodePositions.get(call.node_id)
      ?? demandByNode.get(call.node_id)
      ?? demandByCell.get(call.h3_cell);
    return position ? [{ id: call.id, position, status: call.status, priority: call.priority }] : [];
  });

  return {
    policy: frame?.policy,
    densityCells,
    flowEdges,
    cameras,
    ambulances,
    calls: mergeMapPoints(activeCalls, historicalDemand),
    scenarioImpacts,
  };
}

function latestBy<T extends { bucket_start: string }, K>(
  values: readonly T[],
  key: (value: T) => K,
): T[] {
  const latest = new Map<K, T>();
  values.forEach((value) => {
    const current = latest.get(key(value));
    if (!current || value.bucket_start > current.bucket_start) latest.set(key(value), value);
  });
  return [...latest.values()];
}

function midpoint(start: LongitudeLatitude, end: LongitudeLatitude): LongitudeLatitude {
  return [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2];
}

function spreadCoincidentPoint(position: LongitudeLatitude, occurrence: number): LongitudeLatitude {
  if (occurrence === 0) return position;
  const pointsPerRing = 12;
  const ring = Math.floor((occurrence - 1) / pointsPerRing) + 1;
  const slot = (occurrence - 1) % pointsPerRing;
  const angle = (slot / pointsPerRing) * Math.PI * 2 + ring * 0.31;
  const radius = 0.012 * ring;
  return [
    position[0] + Math.cos(angle) * radius,
    position[1] + Math.sin(angle) * radius,
  ];
}

function mergeMapPoints<T extends { id: string; policy?: "baseline" | "optimized" }>(
  primary: readonly T[],
  fallback: readonly T[],
  policy?: "baseline" | "optimized",
): T[] {
  const points = new Map(fallback.map((point) => [point.id, policy ? { ...point, policy } : point]));
  primary.forEach((point) => points.set(point.id, point));
  return [...primary, ...[...points.values()].filter((point) => !primary.some(({ id }) => id === point.id))];
}

export const CITY_LAYER_IDS = [
  "city-density",
  "city-directional-flow",
  "city-cameras",
  "city-calls",
  "city-ambulances",
  "city-scenario-impact",
] as const;
