"use client";

import { MapboxOverlay } from "@deck.gl/mapbox";
import maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  buildCityLayers,
  DEFAULT_CITY_LAYER_VISIBILITY,
  type CityLayerVisibility,
  type CityMapViewModel,
  type MapSelection,
} from "./layers";
import { MapLegend } from "./legend";
import {
  CITY_MAP_STYLE,
  LOCAL_PMTILES_URL,
  registerLocalPmtiles,
  SAO_PAULO_BOUNDS,
  SAO_PAULO_VIEW,
} from "./map-style";

type MapErrorEvent = { error?: Error };

type MapInstance = {
  on: (event: "error", listener: (event: MapErrorEvent) => void) => void;
  off: (event: "error", listener: (event: MapErrorEvent) => void) => void;
  addControl: (control: DeckOverlay) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  panBy: (offset: [number, number]) => void;
  fitBounds: (
    bounds: [[number, number], [number, number]],
    options: { padding: number; duration: number; maxZoom: number },
  ) => void;
  remove: () => void;
};

type DeckOverlay = {
  setProps: (props: Record<string, unknown>) => void;
  finalize: () => void;
};

export type CityMapRuntime = {
  registerProtocol: () => () => void;
  createMap: (container: HTMLDivElement) => MapInstance;
  createOverlay: (layers: ReturnType<typeof buildCityLayers>) => DeckOverlay;
};

const defaultRuntime: CityMapRuntime = {
  registerProtocol: () => registerLocalPmtiles(maplibregl),
  createMap: (container) => new maplibregl.Map({
    container,
    style: CITY_MAP_STYLE,
    center: [SAO_PAULO_VIEW.longitude, SAO_PAULO_VIEW.latitude],
    zoom: SAO_PAULO_VIEW.zoom,
    minZoom: SAO_PAULO_VIEW.minZoom,
    maxZoom: SAO_PAULO_VIEW.maxZoom,
    maxBounds: SAO_PAULO_BOUNDS.map((position) => [...position]) as [[number, number], [number, number]],
    renderWorldCopies: false,
    attributionControl: false,
    preserveDrawingBuffer: false,
  }) as unknown as MapInstance,
  createOverlay: (layers) => new MapboxOverlay({
    interleaved: true,
    layers,
    useDevicePixels: true,
  }) as unknown as DeckOverlay,
};

export type CityMapProps = {
  viewModel: CityMapViewModel;
  className?: string;
  runtime?: CityMapRuntime;
  onSelectionChange?: (selection: MapSelection | null) => void;
};

function selectionLabel(selection: MapSelection | null): string {
  if (!selection) return "Nenhum elemento selecionado";
  const labels: Record<MapSelection["kind"], string> = {
    cell: "Célula H3",
    flow: "Trecho de fluxo",
    camera: "Câmera",
    ambulance: "Ambulância",
    call: "Chamado",
    impact: "Área de impacto",
  };
  return `${labels[selection.kind]} ${selection.id}`;
}

export function CityMap({
  viewModel,
  className,
  runtime = defaultRuntime,
  onSelectionChange,
}: CityMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapInstance | null>(null);
  const overlayRef = useRef<DeckOverlay | null>(null);
  const [assetError, setAssetError] = useState<string | null>(null);
  const [selection, setSelection] = useState<MapSelection | null>(null);
  const [visibility, setVisibility] = useState<CityLayerVisibility>({
    ...DEFAULT_CITY_LAYER_VISIBILITY,
    ...viewModel.visibility,
  });

  const select = (nextSelection: MapSelection) => {
    setSelection(nextSelection);
    onSelectionChange?.(nextSelection);
    viewModel.onSelect?.(nextSelection);
  };

  const layers = useMemo(
    () => buildCityLayers({ ...viewModel, visibility, onSelect: select }),
    // Each frame is an immutable view-model; visibility is local UI state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [viewModel, visibility],
  );

  useEffect(() => {
    if (!mapContainerRef.current) return;

    const unregister = runtime.registerProtocol();
    const map = runtime.createMap(mapContainerRef.current);
    const overlay = runtime.createOverlay(layers);
    map.addControl(overlay);
    mapRef.current = map;
    overlayRef.current = overlay;
    const showAssetError = (event: MapErrorEvent) => {
      const detail = event.error?.message ? ` (${event.error.message})` : "";
      setAssetError(`Não foi possível carregar o mapa local de São Paulo${detail}.`);
    };

    map.on("error", showAssetError);

    return () => {
      map.off("error", showAssetError);
      overlay.finalize();
      map.remove();
      unregister();
      mapRef.current = null;
      overlayRef.current = null;
    };
    // The runtime is intentionally initialized once for this component instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runtime]);

  useEffect(() => {
    overlayRef.current?.setProps({ layers });
  }, [layers]);

  const toggleLayer = (layer: keyof CityLayerVisibility) => {
    setVisibility((current) => ({ ...current, [layer]: !current[layer] }));
  };

  const navigate = (action: "zoom-in" | "zoom-out" | "left" | "right" | "fit") => {
    const map = mapRef.current;
    if (!map) return;
    if (action === "zoom-in") map.zoomIn();
    if (action === "zoom-out") map.zoomOut();
    if (action === "left") map.panBy([-80, 0]);
    if (action === "right") map.panBy([80, 0]);
    if (action === "fit") map.fitBounds(
      SAO_PAULO_BOUNDS.map((position) => [...position]) as [[number, number], [number, number]],
      { padding: 32, duration: 350, maxZoom: SAO_PAULO_VIEW.zoom },
    );
  };

  return (
    <figure className={className ? `city-map ${className}` : "city-map"} aria-label="Mapa operacional de São Paulo">
      <div className="city-map__viewport">
        <div ref={mapContainerRef} className="city-map__basemap" data-testid="maplibre-container" />
        <div className="city-map__navigation" aria-label="Controles do mapa">
          <button type="button" aria-label="Aumentar zoom" onClick={() => navigate("zoom-in")}>+</button>
          <button type="button" aria-label="Diminuir zoom" onClick={() => navigate("zoom-out")}>−</button>
          <button type="button" aria-label="Enquadrar operação" onClick={() => navigate("fit")}>⌂</button>
          <button type="button" aria-label="Mover mapa para a esquerda" onClick={() => navigate("left")}>←</button>
          <button type="button" aria-label="Mover mapa para a direita" onClick={() => navigate("right")}>→</button>
        </div>
        <MapLegend visibility={visibility} onToggle={toggleLayer} />
        {assetError ? (
          <div className="city-map__error" role="alert">
            <strong>Ativo local indisponível</strong>
            <span>{assetError}</span>
            <code>{LOCAL_PMTILES_URL}</code>
          </div>
        ) : null}
      </div>
      <figcaption aria-live="polite">{selectionLabel(selection)}</figcaption>
    </figure>
  );
}
