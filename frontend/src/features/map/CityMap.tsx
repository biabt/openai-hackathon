"use client";

import { Deck } from "@deck.gl/core";
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
  SAO_PAULO_VIEW,
} from "./map-style";

type MapErrorEvent = { error?: Error };

type MapInstance = {
  on: (event: "move" | "error", listener: (event: MapErrorEvent) => void) => void;
  off: (event: "move" | "error", listener: (event: MapErrorEvent) => void) => void;
  getCenter: () => { lng: number; lat: number };
  getZoom: () => number;
  getBearing: () => number;
  getPitch: () => number;
  remove: () => void;
};

type DeckInstance = {
  setProps: (props: Record<string, unknown>) => void;
  finalize: () => void;
};

export type CityMapRuntime = {
  registerProtocol: () => () => void;
  createMap: (container: HTMLDivElement) => MapInstance;
  createDeck: (container: HTMLDivElement, layers: ReturnType<typeof buildCityLayers>) => DeckInstance;
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
    attributionControl: false,
    preserveDrawingBuffer: false,
  }) as unknown as MapInstance,
  createDeck: (container, layers) => new Deck({
    parent: container,
    width: "100%",
    height: "100%",
    controller: false,
    initialViewState: SAO_PAULO_VIEW,
    layers,
    useDevicePixels: true,
  }) as unknown as DeckInstance,
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
  const deckContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapInstance | null>(null);
  const deckRef = useRef<DeckInstance | null>(null);
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
    if (!mapContainerRef.current || !deckContainerRef.current) return;

    const unregister = runtime.registerProtocol();
    const map = runtime.createMap(mapContainerRef.current);
    const deck = runtime.createDeck(deckContainerRef.current, layers);
    mapRef.current = map;
    deckRef.current = deck;

    const synchronizeCamera = () => {
      const center = map.getCenter();
      deck.setProps({
        viewState: {
          longitude: center.lng,
          latitude: center.lat,
          zoom: map.getZoom(),
          bearing: map.getBearing(),
          pitch: map.getPitch(),
        },
      });
    };
    const showAssetError = (event: MapErrorEvent) => {
      const detail = event.error?.message ? ` (${event.error.message})` : "";
      setAssetError(`Não foi possível carregar o mapa local de São Paulo${detail}.`);
    };

    map.on("move", synchronizeCamera);
    map.on("error", showAssetError);
    synchronizeCamera();

    return () => {
      map.off("move", synchronizeCamera);
      map.off("error", showAssetError);
      deck.finalize();
      map.remove();
      unregister();
      mapRef.current = null;
      deckRef.current = null;
    };
    // The runtime is intentionally initialized once for this component instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runtime]);

  useEffect(() => {
    deckRef.current?.setProps({ layers });
  }, [layers]);

  const toggleLayer = (layer: keyof CityLayerVisibility) => {
    setVisibility((current) => ({ ...current, [layer]: !current[layer] }));
  };

  return (
    <figure className={className ? `city-map ${className}` : "city-map"} aria-label="Mapa operacional de São Paulo">
      <div className="city-map__viewport">
        <div ref={mapContainerRef} className="city-map__basemap" data-testid="maplibre-container" />
        <div ref={deckContainerRef} className="city-map__overlay" data-testid="deck-container" />
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
