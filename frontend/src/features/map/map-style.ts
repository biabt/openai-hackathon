import type { StyleSpecification } from "maplibre-gl";
import { Protocol } from "pmtiles";

export const SAO_PAULO_VIEW = {
  longitude: -46.6333,
  latitude: -23.5505,
  zoom: 10.2,
  minZoom: 8,
  maxZoom: 18,
} as const;

export const LOCAL_PMTILES_URL = "/map/sao-paulo.pmtiles";

export const CITY_MAP_STYLE: StyleSpecification = {
  version: 8,
  name: "City OS — São Paulo offline",
  sources: {
    sao_paulo: {
      type: "vector",
      url: `pmtiles://${LOCAL_PMTILES_URL}`,
      attribution: "© OpenStreetMap contributors · artefato local",
    },
  },
  layers: [
    { id: "background", type: "background", paint: { "background-color": "#07111f" } },
    {
      id: "local-landuse",
      type: "fill",
      source: "sao_paulo",
      "source-layer": "landuse",
      paint: { "fill-color": "#132235", "fill-opacity": 0.65 },
    },
    {
      id: "local-water",
      type: "fill",
      source: "sao_paulo",
      "source-layer": "water",
      paint: { "fill-color": "#123451", "fill-opacity": 0.92 },
    },
    {
      id: "local-roads",
      type: "line",
      source: "sao_paulo",
      "source-layer": "roads",
      paint: {
        "line-color": ["interpolate", ["linear"], ["zoom"], 8, "#32465e", 14, "#6e8198"],
        "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.4, 15, 2.4],
        "line-opacity": 0.9,
      },
    },
  ],
};

type ProtocolMapLibre = {
  addProtocol: (name: string, handler: Protocol["tile"]) => void;
  removeProtocol?: (name: string) => void;
};

let protocolUsers = 0;
let protocol: Protocol | null = null;

export function registerLocalPmtiles(maplibre: ProtocolMapLibre): () => void {
  if (protocolUsers === 0) {
    protocol = new Protocol();
    maplibre.addProtocol("pmtiles", protocol.tile);
  }
  protocolUsers += 1;

  return () => {
    protocolUsers = Math.max(0, protocolUsers - 1);
    if (protocolUsers === 0) {
      maplibre.removeProtocol?.("pmtiles");
      protocol = null;
    }
  };
}
