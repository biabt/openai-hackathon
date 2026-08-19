import type { DensityCell, FlowEdge, LongitudeLatitude, MapCamera } from "./layers";

/** Small, geographically plausible São Paulo fixture used only by the video mock. */
export const MOCK_NODE_POSITIONS: Readonly<Record<number, LongitudeLatitude>> = {
  1: [-46.6602, -23.5536], // Consolação
  2: [-46.6333, -23.5505], // Sé
  3: [-46.5764, -23.5403], // Tatuapé
  10: [-46.6351, -23.5892], // Vila Mariana
  20: [-46.5218, -23.5660], // Aricanduva
};

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
