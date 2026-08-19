export type ScenarioCardModel = {
  id: string;
  type: "flood" | "event" | "blocked_road" | string;
  title: string;
  summary: string;
  startsAt: string;
  endsAt: string;
  location: string;
  impact: string;
  confidence: number;
  source: "simulated";
};

export type ScenarioCardProps = {
  scenario: ScenarioCardModel;
  selected: boolean;
  state?: "available" | "queued" | "active";
  onSelect: (scenario: ScenarioCardModel) => void;
};

const STATE_LABELS = {
  available: "Disponível",
  queued: "Na fila",
  active: "Ativo",
} as const;

export function ScenarioCard({
  scenario,
  selected,
  state = "available",
  onSelect,
}: ScenarioCardProps) {
  const stateLabel = STATE_LABELS[state];
  return (
    <article
      className={`scenario-card scenario-card--${state}${selected ? " scenario-card--selected" : ""}`}
      aria-label={`${scenario.title}: ${stateLabel}`}
    >
      <button
        type="button"
        className="scenario-card__select"
        aria-pressed={selected}
        onClick={() => onSelect(scenario)}
      >
        <span className="scenario-card__heading">
          <strong>{scenario.title}</strong>
          <span className={`scenario-card__state scenario-card__state--${state}`}>{stateLabel}</span>
        </span>
        <span>{scenario.summary}</span>
        <dl className="scenario-card__details">
          <div>
            <dt>Quando</dt>
            <dd>{scenario.startsAt}–{scenario.endsAt}</dd>
          </div>
          <div>
            <dt>Onde</dt>
            <dd>{scenario.location}</dd>
          </div>
          <div>
            <dt>Impacto</dt>
            <dd>{scenario.impact}</dd>
          </div>
        </dl>
        <span className="scenario-card__provenance">
          Fonte simulada · confiança {Math.round(scenario.confidence * 100)}%
        </span>
      </button>
    </article>
  );
}

