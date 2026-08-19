import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CityMap, type CityMapRuntime } from "./CityMap";
import { buildCityLayers, CITY_LAYER_IDS, createCityMapViewModel, type MapAmbulance } from "./layers";
import { CITY_MAP_STYLE, LOCAL_PMTILES_URL } from "./map-style";

const position = [-46.6333, -23.5505] as const;

function fakeRuntime() {
  const listeners = new Map<string, (event: { error?: Error }) => void>();
  const deckSetProps = vi.fn();
  const createDeck = vi.fn<CityMapRuntime["createDeck"]>(() => ({
    setProps: deckSetProps,
    finalize: vi.fn(),
  }));
  const runtime: CityMapRuntime = {
    registerProtocol: vi.fn(() => vi.fn()),
    createMap: vi.fn(() => ({
      on: vi.fn((name, listener) => listeners.set(name, listener)),
      off: vi.fn(),
      getCenter: () => ({ lng: position[0], lat: position[1] }),
      getZoom: () => 10,
      getBearing: () => 0,
      getPitch: () => 0,
      remove: vi.fn(),
    })),
    createDeck,
  };
  return { runtime, listeners, deckSetProps, createDeck };
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
    expect(model.cameras).toHaveLength(4);
    expect(model.flowEdges).toHaveLength(4);
    expect(model.densityCells).toHaveLength(1);
    expect(model.scenarioImpacts?.[0]).toMatchObject({ h3Index: "88a8100c05fffff" });
  });
});

describe("CityMap", () => {
  it("toggles layers and selects an ambulance without WebGL", async () => {
    const { runtime, createDeck, deckSetProps } = fakeRuntime();
    render(<CityMap runtime={runtime} viewModel={{ ambulances: [{ id: "AMB-1", position }] }} />);

    const initialLayers = createDeck.mock.calls[0]![1];
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
});
