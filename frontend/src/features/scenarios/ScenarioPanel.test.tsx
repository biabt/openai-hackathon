import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CityOsTransport } from "@/lib/api/transport";
import type { ScenarioObservation, SimulationRequest } from "@/lib/contracts/generated";
import { FleetControl } from "../simulation/FleetControl";
import { ScenarioPanel } from "./ScenarioPanel";
import { SensorComposer } from "./SensorComposer";

const observation: ScenarioObservation = {
  id: "flood-aricanduva-1730",
  type: "flood",
  starts_at: "17:30",
  ends_at: "19:00",
  affected_h3: ["88a8100c05fffff"],
  demand_multiplier: 1.25,
  travel_penalty: 2,
  blocked_edges: [12345],
  confidence: 0.9,
  source: "simulated",
};

describe("ScenarioPanel", () => {
  it("selects one scenario and shows time, place, impact and provenance", () => {
    const onSelect = vi.fn();
    render(
      <ScenarioPanel
        selectedScenarioId="normal-weekday"
        queuedScenarioId="flood-aricanduva-1730"
        onSelectScenario={onSelect}
      />,
    );

    const flood = screen.getByRole("button", { name: /Alagamento no Aricanduva/i });
    expect(flood).toHaveTextContent("17:30–19:00");
    expect(flood).toHaveTextContent("Zona Leste");
    expect(flood).toHaveTextContent("2× custo viário");
    expect(flood).toHaveTextContent("Fonte simulada · confiança 90%");
    expect(screen.getByLabelText(/Alagamento no Aricanduva: Na fila/i)).toBeInTheDocument();
    fireEvent.click(flood);
    expect(onSelect).toHaveBeenCalledWith("flood-aricanduva-1730");
  });
});

describe("SensorComposer", () => {
  it("parses a typed observation through the transport", async () => {
    const parseScenarioCard = vi.fn().mockResolvedValue(observation);
    const onParsed = vi.fn();
    const transport = { parseScenarioCard } as Pick<CityOsTransport, "parseScenarioCard">;
    render(<SensorComposer transport={transport} onParsed={onParsed} />);

    fireEvent.change(screen.getByLabelText("Mensagem do sensor simulado"), {
      target: { value: "alagamento no Aricanduva entre 17:30 e 19:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Interpretar observação" }));
    await waitFor(() => expect(onParsed).toHaveBeenCalledWith(observation));
    expect(parseScenarioCard).toHaveBeenCalledWith("alagamento no Aricanduva entre 17:30 e 19:00");
    expect(screen.getByRole("status")).toHaveTextContent("fonte simulada");
  });

  it("keeps parser errors visible", async () => {
    const transport = {
      parseScenarioCard: vi.fn().mockRejectedValue(new Error("fora do contrato")),
    } as Pick<CityOsTransport, "parseScenarioCard">;
    render(<SensorComposer transport={transport} onParsed={vi.fn()} initialText="mensagem inválida" />);
    fireEvent.click(screen.getByRole("button", { name: "Interpretar observação" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("fora do contrato");
  });
});

describe("FleetControl", () => {
  it("changes the draft fleet but sends it only on Run", () => {
    const onRun = vi.fn<(request: SimulationRequest) => void>();
    render(
      <FleetControl
        scenarioId="flood-aricanduva-1730"
        initialFleetSize={80}
        seed={42}
        onRun={onRun}
      />,
    );
    const slider = screen.getByRole("slider", { name: "Tamanho da frota" });
    fireEvent.change(slider, { target: { value: "120" } });
    expect(screen.getByText("120 ambulâncias")).toBeInTheDocument();
    expect(onRun).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Executar comparação" }));
    expect(onRun).toHaveBeenCalledWith({
      scenario_id: "flood-aricanduva-1730",
      fleet_size: 120,
      seed: 42,
    });
  });
});

