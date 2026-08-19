import type { CityLayerVisibility } from "./layers";

const LAYERS: ReadonlyArray<{
  key: keyof CityLayerVisibility;
  label: string;
  source: string;
  color: string;
}> = [
  { key: "density", label: "Densidade H3", source: "inferida", color: "#ffb84d" },
  { key: "flow", label: "Fluxo viário", source: "inferido", color: "#38bdf8" },
  { key: "cameras", label: "Câmeras", source: "observado", color: "#d8b4fe" },
  { key: "ambulances", label: "Ambulâncias", source: "simulado", color: "#2dd4bf" },
  { key: "calls", label: "Chamados", source: "sintético", color: "#facc15" },
  { key: "impact", label: "Impacto do evento", source: "simulado", color: "#ef4444" },
];

export type MapLegendProps = {
  visibility: CityLayerVisibility;
  onToggle: (layer: keyof CityLayerVisibility) => void;
};

export function MapLegend({ visibility, onToggle }: MapLegendProps) {
  return (
    <fieldset className="map-legend" aria-label="Camadas do mapa">
      <legend>Camadas</legend>
      {LAYERS.map((layer) => (
        <label key={layer.key} className="map-legend__item">
          <input
            type="checkbox"
            checked={visibility[layer.key]}
            onChange={() => onToggle(layer.key)}
          />
          <span aria-hidden="true" className="map-legend__swatch" style={{ background: layer.color }} />
          <span>{layer.label}</span>
          <small>{layer.source}</small>
        </label>
      ))}
    </fieldset>
  );
}

