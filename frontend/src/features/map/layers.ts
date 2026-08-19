import { PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import type { Layer, PickingInfo } from "@deck.gl/core";
import type { BootstrapResponse, SimulationFrame } from "@/lib/contracts/generated";
import { MOCK_CAMERAS, MOCK_DENSITY, MOCK_FLOW_EDGES, MOCK_NODE_POSITIONS } from "./map-fixture";

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
    new ScatterplotLayer<MapAmbulance>({
      id: "city-ambulances",
      data: [...(viewModel.ambulances ?? [])],
      visible: visibility.ambulances,
      pickable: true,
      radiusUnits: "pixels",
      getRadius: 7,
      getPosition: (ambulance) => ambulance.position as [number, number],
      getFillColor: (ambulance) => ambulanceColor(ambulance.policy ?? policy),
      getLineColor: [255, 255, 255, 255],
      lineWidthMinPixels: 2,
      stroked: true,
      onClick: selectionHandler("ambulance", (ambulance: MapAmbulance) => ambulance.id, viewModel.onSelect),
      updateTriggers: { getFillColor: [policy] },
    }),
    new ScatterplotLayer<MapCall>({
      id: "city-calls",
      data: [...(viewModel.calls ?? [])],
      visible: visibility.calls,
      pickable: true,
      radiusUnits: "pixels",
      getRadius: 6,
      getPosition: (call) => call.position as [number, number],
      getFillColor: (call) => call.status === "QUEUED" ? [239, 68, 68, 255] : [250, 204, 21, 245],
      getLineColor: [17, 24, 39, 255],
      lineWidthMinPixels: 1,
      stroked: true,
      onClick: selectionHandler("call", (call: MapCall) => call.id, viewModel.onSelect),
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
): CityMapViewModel {
  const scenarioImpacts = (frame?.active_scenario_ids ?? []).flatMap((scenarioId) => {
    const scenario = bootstrap.scenarios.find((item) => item.id === scenarioId);
    return (scenario?.affected_h3 ?? []).map((h3Index) => ({
      id: `${scenarioId}:${h3Index}`,
      h3Index,
      type: scenario?.type,
    }));
  });

  return {
    policy: frame?.policy,
    densityCells: MOCK_DENSITY,
    flowEdges: MOCK_FLOW_EDGES,
    cameras: MOCK_CAMERAS,
    ambulances: (frame?.ambulances ?? []).flatMap((ambulance) => {
      const position = MOCK_NODE_POSITIONS[ambulance.node_id];
      return position ? [{ id: ambulance.id, position, policy: frame?.policy, status: ambulance.status }] : [];
    }),
    calls: (frame?.calls ?? []).flatMap((call) => {
      const position = MOCK_NODE_POSITIONS[call.node_id];
      return position ? [{ id: call.id, position, status: call.status, priority: call.priority }] : [];
    }),
    scenarioImpacts,
  };
}

export const CITY_LAYER_IDS = [
  "city-density",
  "city-directional-flow",
  "city-cameras",
  "city-ambulances",
  "city-calls",
  "city-scenario-impact",
] as const;
