import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CityMap, type CityMapRuntime } from "./CityMap";
import { buildCityLayers, CITY_LAYER_IDS, createCityMapViewModel, type MapAmbulance } from "./layers";
import { CITY_MAP_STYLE, LOCAL_PMTILES_URL } from "./map-style";

const position = [-46.6333, -23.5505] as const;

function fakeRuntime() {
  const listeners = new Map<string, (event: { error?: Error }) => void>();
  const deckSetProps = vi.fn();
  const zoomIn = vi.fn();
  const zoomOut = vi.fn();
  const panBy = vi.fn();
  const fitBounds = vi.fn();
  const addControl = vi.fn();
  const createOverlay = vi.fn<CityMapRuntime["createOverlay"]>(() => ({
    setProps: deckSetProps,
    finalize: vi.fn(),
  }));
  const runtime: CityMapRuntime = {
    registerProtocol: vi.fn(() => vi.fn()),
    createMap: vi.fn(() => ({
      on: vi.fn((name, listener) => listeners.set(name, listener)),
      off: vi.fn(),
      addControl,
      zoomIn,
      zoomOut,
      panBy,
      fitBounds,
      remove: vi.fn(),
    })),
    createOverlay,
  };
  return {
    runtime, listeners, deckSetProps, createOverlay, addControl, zoomIn, zoomOut, panBy, fitBounds,
  };
}

describe("buildCityLayers", () => {
  it("keeps stable IDs and is safe with empty data", () => {
    const layers = buildCityLayers({});
    expect(layers.map((layer) => layer.id)).toEqual(CITY_LAYER_IDS);
    for (const layer of layers) expect(layer.props.data).toEqual([]);
  });

  it("uses policy-specific ambulance colors and exposes picking data", () => {
    const onSelect = vi.fn();
    const ambulance: MapAmbulance = { id: "A-7", position, policy: "baseline" };
    const layers = buildCityLayers({ ambulances: [ambulance], onSelect });
    const ambulanceLayer = layers.find((layer) => layer.id === "city-ambulances")!;
    const optimizedLayers = buildCityLayers({
      ambulances: [{ ...ambulance, policy: "optimized" }],
    });
    const optimizedLayer = optimizedLayers.find((layer) => layer.id === "city-ambulances")!;

    const baselineColor = (ambulanceLayer.props as never as { getFillColor: (item: MapAmbulance) => number[] })
      .getFillColor(ambulance);
    const optimizedColor = (optimizedLayer.props as never as { getFillColor: (item: MapAmbulance) => number[] })
      .getFillColor({ ...ambulance, policy: "optimized" });
    expect(baselineColor).not.toEqual(optimizedColor);

    (ambulanceLayer.props as never as { onClick: (info: { object: MapAmbulance }) => void })
      .onClick({ object: ambulance });
    expect(onSelect).toHaveBeenCalledWith({ kind: "ambulance", id: "A-7", datum: ambulance });
  });

  it("references only the bundled PMTiles source", () => {
    expect(JSON.stringify(CITY_MAP_STYLE)).toContain(`pmtiles://${LOCAL_PMTILES_URL}`);
    expect(JSON.stringify(CITY_MAP_STYLE)).not.toMatch(/https?:\/\//);
  });

  it("adapts the local video fixture and scenario impacts", () => {
    const bootstrap = {
      scenarios: [{
        id: "event-1", type: "event", starts_at: "18:00", ends_at: "19:00",
        affected_h3: ["88a8100c05fffff"], demand_multiplier: 1.2, travel_penalty: 1,
        blocked_edges: [], confidence: 0.9, source: "simulated",
      }],
    } as never;
    const frame = {
      policy: "optimized",
      ambulances: [{ id: "A-1", node_id: 1, status: "available", target_node_id: null, call_id: null }],
      calls: [], active_scenario_ids: ["event-1"],
    } as never;
    const model = createCityMapViewModel(bootstrap, frame);
    expect(model.ambulances?.[0]).toMatchObject({ id: "A-1", position: [-46.6602, -23.5536] });
    expect(model.ambulances).toHaveLength(36);
    expect(model.calls).toHaveLength(40);
    expect(model.cameras).toHaveLength(4);
    expect(model.flowEdges).toHaveLength(4);
    expect(model.densityCells).toHaveLength(1);
    expect(model.scenarioImpacts?.[0]).toMatchObject({ h3Index: "88a8100c05fffff" });
  });
});

describe("CityMap", () => {
  it("toggles layers and selects an ambulance without WebGL", async () => {
    const { runtime, createOverlay, addControl, deckSetProps } = fakeRuntime();
    render(<CityMap runtime={runtime} viewModel={{ ambulances: [{ id: "AMB-1", position }] }} />);

    const initialLayers = createOverlay.mock.calls[0]![0];
    expect(addControl).toHaveBeenCalledOnce();
    const ambulanceLayer = initialLayers.find((layer: { id: string }) => layer.id === "city-ambulances")!;
    act(() => {
      (ambulanceLayer.props as never as { onClick: (info: { object: MapAmbulance }) => void })
        .onClick({ object: { id: "AMB-1", position } });
    });
    expect(screen.getByText("Ambulância AMB-1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: /Densidade H3/i }));
    await waitFor(() => {
      const calls = deckSetProps.mock.calls;
      const last = calls[calls.length - 1]![0] as { layers: ReturnType<typeof buildCityLayers> };
      const density = last.layers.find((layer) => layer.id === "city-density");
      expect(density?.props.visible).toBe(false);
    });
  });

  it("shows a visible error when the local asset fails", () => {
    const { runtime, listeners } = fakeRuntime();
    render(<CityMap runtime={runtime} viewModel={{}} />);
    act(() => listeners.get("error")?.({ error: new Error("arquivo ausente") }));
    expect(screen.getByRole("alert")).toHaveTextContent("Ativo local indisponível");
    expect(screen.getByRole("alert")).toHaveTextContent(LOCAL_PMTILES_URL);
  });

  it("shows the expanded ambulance and demand fixtures before a simulation starts", () => {
    const model = createCityMapViewModel({ scenarios: [] } as never);
    expect(model.ambulances).toHaveLength(35);
    expect(model.calls).toHaveLength(40);
    expect(new Set(model.ambulances?.map(({ id }) => id)).size).toBe(35);
    expect(new Set(model.calls?.map(({ id }) => id)).size).toBe(40);
  });

  it("maps every operational layer exclusively from API semantic data", () => {
    const model = createCityMapViewModel({ scenarios: [] } as never, {
      policy: "optimized",
      ambulances: [
        { id: "amb-001", node_id: 101, status: "available", target_node_id: null, call_id: null },
        { id: "amb-002", node_id: 101, status: "available", target_node_id: null, call_id: null },
      ],
      calls: [{
        id: "call-live", node_id: 102, h3_cell: "88a8100c03fffff", priority: 1,
        status: "dispatched", occurred_at_minute: 5, response_seconds: null,
      }],
      active_scenario_ids: [],
    } as never, {
      nodes: [
        { node_id: 101, x: -46.63, y: -23.55, h3_cell: "88a8100c03fffff" },
        { node_id: 102, x: -46.62, y: -23.54, h3_cell: "88a8100c03fffff" },
      ],
      edges: [{
        edge_id: 501, u: 101, v: 102, capacity_vph: 9_999,
        free_flow_seconds: 10, geometry_wkb: "", length_m: 100,
      }],
      h3Cells: [{ cell: "88a8100c03fffff", geometry: {} }],
      cameraObservations: [{
        camera_id: "cam-api", edge_id: 501, bucket_start: "2026-08-19T12:00:00Z",
        object_class: "car", direction: "northbound", count: 12, confidence: 0.9,
      }],
      edgeStates: [{
        edge_id: 501, bucket_start: "2026-08-19T12:00:00Z", flow_vph: 432,
        speed_kph: 28, travel_seconds: 15, occupancy_people: 9, confidence: 0.8,
      }],
      densities: [{
        cell: "88a8100c03fffff", bucket_start: "2026-08-19T12:00:00Z",
        density_people_km2: 3400, emergency_intensity_hour: 2.1, confidence: 0.7,
      }],
      demandPoints: [{
        id: "demand-api", node_id: 102, h3_cell: "88a8100c03fffff",
        longitude: -46.62, latitude: -23.54, historical_occurrences: 23,
        injured: 7, fatalities: 1, weight: 0.75,
      }],
    });

    expect(model.flowEdges).toEqual([{
      id: 501, path: [[-46.63, -23.55], [-46.62, -23.54]], flow: 432, confidence: 0.8,
    }]);
    expect(model.densityCells).toHaveLength(1);
    expect(model.densityCells?.[0]?.density).toBe(3400);
    expect(model.cameras).toEqual([{
      id: "cam-api", position: [-46.625, -23.545], confidence: 0.9,
    }]);
    expect(model.ambulances).toHaveLength(2);
    expect(model.ambulances?.slice(0, 2).map(({ id }) => id)).toEqual(["amb-001", "amb-002"]);
    expect(model.calls?.map(({ id }) => id)).toEqual(["call-live", "demand-api"]);
  });

  it("keeps every API operational layer empty instead of adding fixtures", () => {
    const model = createCityMapViewModel(
      { scenarios: [] } as never,
      null,
      null,
      { source: "api" },
    );

    expect(model.ambulances).toEqual([]);
    expect(model.calls).toEqual([]);
    expect(model.cameras).toEqual([]);
    expect(model.flowEdges).toEqual([]);
    expect(model.densityCells).toEqual([]);
  });

  it("never invents an ambulance position when its API node is absent", () => {
    const ambulances = [
      { id: "amb-known", node_id: 1, status: "available", target_node_id: null, call_id: null },
      { id: "amb-unknown", node_id: 10_000, status: "available", target_node_id: null, call_id: null },
    ];
    const model = createCityMapViewModel(
      { scenarios: [] } as never,
      { policy: "optimized", ambulances, calls: [], active_scenario_ids: [] } as never,
      {
        nodes: [{ node_id: 1, x: -46.63, y: -23.55, h3_cell: "88a8100c03fffff" }],
        edges: [],
        h3Cells: [],
        cameraObservations: [],
        edgeStates: [],
        densities: [],
        demandPoints: [],
      },
    );

    expect(model.ambulances).toEqual([{
      id: "amb-known", position: [-46.63, -23.55], policy: "optimized", status: "available",
    }]);
  });

  it("zooms, pans and synchronizes drag navigation with the basemap", () => {
    const { runtime, zoomIn, zoomOut, panBy, fitBounds } = fakeRuntime();
    render(<CityMap runtime={runtime} viewModel={{}} />);

    fireEvent.click(screen.getByRole("button", { name: "Aumentar zoom" }));
    fireEvent.click(screen.getByRole("button", { name: "Diminuir zoom" }));
    fireEvent.click(screen.getByRole("button", { name: "Mover mapa para a esquerda" }));
    fireEvent.click(screen.getByRole("button", { name: "Mover mapa para a direita" }));
    fireEvent.click(screen.getByRole("button", { name: "Enquadrar operação" }));

    expect(zoomIn).toHaveBeenCalledOnce();
    expect(zoomOut).toHaveBeenCalledOnce();
    expect(panBy).toHaveBeenNthCalledWith(1, [-80, 0]);
    expect(panBy).toHaveBeenNthCalledWith(2, [80, 0]);
    expect(fitBounds).toHaveBeenCalledOnce();
  });
});
