import type {
  DensityCell,
  FlowEdge,
  LongitudeLatitude,
  MapAmbulance,
  MapCall,
  MapCamera,
} from "./layers";

/** Small, geographically plausible São Paulo fixture used only by the video mock. */
export const MOCK_NODE_POSITIONS: Readonly<Record<number, LongitudeLatitude>> = {
  1: [-46.6602, -23.5536], // Consolação
  2: [-46.6333, -23.5505], // Sé
  3: [-46.5764, -23.5403], // Tatuapé
  4: [-46.6817, -23.5617], // Pinheiros
  5: [-46.7042, -23.5281], // Lapa
  6: [-46.6246, -23.5015], // Santana
  7: [-46.6991, -23.6493], // Santo Amaro
  8: [-46.6639, -23.6019], // Moema
  9: [-46.6074, -23.5851], // Ipiranga
  10: [-46.6351, -23.5892], // Vila Mariana
  11: [-46.4741, -23.5416], // Itaquera
  12: [-46.4397, -23.4938], // São Miguel Paulista
  13: [-46.7219, -23.5718], // Butantã
  14: [-46.7582, -23.6326], // Campo Limpo
  15: [-46.7068, -23.7095], // Capela do Socorro
  16: [-46.7273, -23.8245], // Parelheiros
  17: [-46.5336, -23.5228], // Penha
  18: [-46.5986, -23.5602], // Mooca
  19: [-46.6404, -23.6472], // Jabaquara
  20: [-46.5218, -23.5660], // Aricanduva
  21: [-46.4102, -23.5507], // Guaianases
  22: [-46.6901, -23.4622], // Brasilândia
  23: [-46.7282, -23.4857], // Pirituba
  24: [-46.5795, -23.5948], // Vila Prudente
};

const BASE_POSITIONS = Object.values(MOCK_NODE_POSITIONS);

function distributedPosition(index: number, stride: number, separation = 0): LongitudeLatitude {
  const base = BASE_POSITIONS[(index * stride) % BASE_POSITIONS.length]!;
  const lap = Math.floor(index / BASE_POSITIONS.length);
  if (lap === 0 && separation === 0) return base;
  const angle = index * 2.399963229728653;
  const radius = separation + 0.01 * lap;
  return [base[0] + Math.cos(angle) * radius, base[1] + Math.sin(angle) * radius];
}

export const MOCK_AMBULANCES: readonly MapAmbulance[] = Array.from({ length: 35 }, (_, index) => ({
  id: `amb-${String(index + 1).padStart(3, "0")}`,
  position: distributedPosition(index, 5),
  status: "available",
}));

/** Synthetic demand nodes shown as calls so the city has a useful pre-run demand field. */
export const MOCK_DEMAND_NODES: readonly MapCall[] = Array.from({ length: 40 }, (_, index) => ({
  id: `demand-${String(index + 1).padStart(3, "0")}`,
  position: distributedPosition(index, 7, 0.007),
  status: "forecast",
  priority: 1 + index % 3,
}));

export const MOCK_CAMERAS: readonly MapCamera[] = [
  { id: "CAM-PAULISTA", position: [-46.6579, -23.5614], confidence: 0.96 },
  { id: "CAM-RADIAL", position: [-46.5908, -23.5483], confidence: 0.91 },
  { id: "CAM-ARICANDUVA", position: [-46.5327, -23.5608], confidence: 0.94 },
  { id: "CAM-23-MAIO", position: [-46.6388, -23.5822], confidence: 0.89 },
];

export const MOCK_FLOW_EDGES: readonly FlowEdge[] = [
  { id: "paulista-centro", path: [[-46.6602, -23.5536], [-46.6333, -23.5505]], flow: 920, confidence: 0.92 },
  { id: "centro-tatuape", path: [[-46.6333, -23.5505], [-46.5764, -23.5403]], flow: 1_140, confidence: 0.88 },
  { id: "tatuape-aricanduva", path: [[-46.5764, -23.5403], [-46.5218, -23.5660]], flow: 780, confidence: 0.9 },
  { id: "vila-mariana-centro", path: [[-46.6351, -23.5892], [-46.6333, -23.5505]], flow: 640, confidence: 0.86 },
];

export const MOCK_DENSITY: readonly DensityCell[] = [
  { h3_index: "88a8100c05fffff", density: 86, confidence: 0.9 },
];
