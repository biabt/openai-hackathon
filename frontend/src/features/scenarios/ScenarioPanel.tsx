"use client";

import { ScenarioCard, type ScenarioCardModel } from "./ScenarioCard";
import type { ScenarioObservation } from "@/lib/contracts/generated";

const TYPE_TITLES: Record<ScenarioObservation["type"], string> = {
  flood: "Alagamento",
  event: "Evento de grande porte",
  demonstration: "Manifestação",
  transit_disruption: "Interrupção de transporte",
};

export function scenarioCardsFromObservations(
  observations: readonly ScenarioObservation[],
): ScenarioCardModel[] {
  return observations.map((observation) => ({
    id: observation.id,
    type: observation.type,
    title: TYPE_TITLES[observation.type],
    summary: "Observação estruturada do sensor de cenários da demonstração.",
    startsAt: observation.starts_at,
    endsAt: observation.ends_at,
    location: observation.affected_h3.length
      ? `${observation.affected_h3.length} célula(s) H3 afetada(s)`
      : `${observation.blocked_edges.length} trecho(s) viário(s) afetado(s)`,
    impact: `${observation.demand_multiplier.toLocaleString("pt-BR")}× demanda · ${observation.travel_penalty.toLocaleString("pt-BR")}× custo viário`,
    confidence: observation.confidence,
    source: observation.source,
  }));
}

export const BUILT_IN_SCENARIOS: readonly ScenarioCardModel[] = [
  {
    id: "normal-weekday",
    type: "event",
    title: "Operação normal",
    summary: "Dia útil sem choque adicional de demanda ou circulação.",
    startsAt: "14:00",
    endsAt: "20:00",
    location: "Município de São Paulo",
    impact: "Referência para a comparação pareada",
    confidence: 1,
    source: "simulated",
  },
  {
    id: "concert-allianz-1800",
    type: "event",
    title: "Show no Allianz Parque",
    summary: "Concentração futura de público e pressão de demanda no entorno.",
    startsAt: "18:00",
    endsAt: "20:00",
    location: "Allianz Parque · Água Branca",
    impact: "+40% de demanda na área afetada",
    confidence: 0.88,
    source: "simulated",
  },
  {
    id: "flood-aricanduva-1730",
    type: "flood",
    title: "Alagamento no Aricanduva",
    summary: "Vias degradadas alteram rotas e elevam o tempo de deslocamento.",
    startsAt: "17:30",
    endsAt: "19:00",
    location: "Eixo do Aricanduva · Zona Leste",
    impact: "1,25× demanda · 2× custo viário",
    confidence: 0.9,
    source: "simulated",
  },
  {
    id: "blocked-road-center-1630",
    type: "demonstration",
    title: "Via bloqueada no Centro",
    summary: "Interdição demonstrativa exige desvio das ambulâncias.",
    startsAt: "16:30",
    endsAt: "18:00",
    location: "Região da Sé · Centro",
    impact: "Bloqueio de trechos e recálculo de ETA",
    confidence: 0.84,
    source: "simulated",
  },
] as const;

export type ScenarioPanelProps = {
  scenarios?: readonly ScenarioCardModel[];
  selectedScenarioId: string;
  activeScenarioIds?: readonly string[];
  queuedScenarioId?: string | null;
  onSelectScenario: (scenarioId: string) => void;
};

export function ScenarioPanel({
  scenarios = BUILT_IN_SCENARIOS,
  selectedScenarioId,
  activeScenarioIds = [],
  queuedScenarioId,
  onSelectScenario,
}: ScenarioPanelProps) {
  const select = (scenario: ScenarioCardModel) => onSelectScenario(scenario.id);

  return (
    <section className="scenario-panel" aria-labelledby="scenario-panel-title">
      <header>
        <p className="eyebrow">Sensor de cenários</p>
        <h2 id="scenario-panel-title">Choques urbanos simulados</h2>
        <p>Todos os cards são entradas determinísticas da demonstração, não alertas ao vivo.</p>
      </header>
      <div className="scenario-panel__cards" role="list">
        {scenarios.map((scenario) => {
          const state = activeScenarioIds.includes(scenario.id)
            ? "active"
            : queuedScenarioId === scenario.id
              ? "queued"
              : "available";
          return (
            <div role="listitem" key={scenario.id}>
              <ScenarioCard
                scenario={scenario}
                selected={scenario.id === selectedScenarioId}
                state={state}
                onSelect={select}
              />
            </div>
          );
        })}
      </div>
    </section>
  );
}
