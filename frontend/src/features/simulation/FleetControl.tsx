"use client";

import { useEffect, useState } from "react";
import type { SimulationRequest } from "@/lib/contracts/generated";

export type FleetControlProps = {
  scenarioId: string;
  initialFleetSize?: number;
  minimum?: number;
  maximum?: number;
  seed?: number;
  disabled?: boolean;
  onFleetSizeChange?: (fleetSize: number) => void;
  onRun: (request: SimulationRequest) => void;
};

export function FleetControl({
  scenarioId,
  initialFleetSize = 80,
  minimum = 20,
  maximum = 200,
  seed = 42,
  disabled = false,
  onFleetSizeChange,
  onRun,
}: FleetControlProps) {
  const [fleetSize, setFleetSize] = useState(initialFleetSize);

  useEffect(() => {
    setFleetSize(initialFleetSize);
  }, [initialFleetSize]);

  useEffect(() => {
    if (!onFleetSizeChange) return;
    const timeout = window.setTimeout(() => onFleetSizeChange(fleetSize), 180);
    return () => window.clearTimeout(timeout);
  }, [fleetSize, onFleetSizeChange]);

  const run = () => {
    onRun({ scenario_id: scenarioId, fleet_size: fleetSize, seed });
  };

  return (
    <section className="fleet-control" aria-labelledby="fleet-control-title">
      <div className="fleet-control__heading">
        <div>
          <p className="eyebrow">Capacidade operacional</p>
          <h2 id="fleet-control-title">Frota</h2>
        </div>
        <output htmlFor="fleet-size" aria-live="polite">{fleetSize} ambulâncias</output>
      </div>
      <label htmlFor="fleet-size">Tamanho da frota</label>
      <input
        id="fleet-size"
        type="range"
        min={minimum}
        max={maximum}
        step={1}
        value={fleetSize}
        disabled={disabled}
        aria-valuetext={`${fleetSize} ambulâncias`}
        onChange={(event) => setFleetSize(Number(event.target.value))}
      />
      <div className="fleet-control__range" aria-hidden="true">
        <span>{minimum}</span>
        <span>{maximum}</span>
      </div>
      <p>Seed determinística: <code>{seed}</code></p>
      <button type="button" onClick={run} disabled={disabled || !scenarioId}>
        Executar comparação
      </button>
      <small>A simulação só recebe o valor quando você executa; arrastar não inicia uma nova rodada.</small>
    </section>
  );
}

