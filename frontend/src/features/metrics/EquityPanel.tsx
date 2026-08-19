import React from "react";

import type { SimulationMetrics } from "../../lib/contracts/generated";

function formatMinutes(seconds: number | null): string {
  return seconds == null ? "Sem dados" : `${(seconds / 60).toFixed(1)} min`;
}

export interface EquityPanelProps {
  baseline: SimulationMetrics;
  optimized: SimulationMetrics;
}

export function EquityPanel({ baseline, optimized }: EquityPanelProps) {
  const before = baseline.worst_district_p90_seconds;
  const after = optimized.worst_district_p90_seconds;
  const delta = before == null || after == null ? null : before - after;
  const improved = delta != null && delta > 0;
  const worsened = delta != null && delta < 0;

  return (
    <section aria-labelledby="equity-title" className="equity-panel">
      <div>
        <p className="eyebrow">Equidade territorial</p>
        <h3 id="equity-title">P90 do distrito mais crítico</h3>
      </div>
      <dl>
        <div>
          <dt>Antes</dt>
          <dd>{formatMinutes(before)}</dd>
        </div>
        <div>
          <dt>Depois</dt>
          <dd>{formatMinutes(after)}</dd>
        </div>
      </dl>
      <p
        data-tone={improved ? "positive" : worsened ? "negative" : "neutral"}
        style={{ color: improved ? "#22a06b" : worsened ? "#d14343" : "currentColor" }}
      >
        {delta == null
          ? "Aguardando dados de equidade"
          : improved
          ? `${formatMinutes(delta)} menor no pior distrito`
          : worsened
            ? `${formatMinutes(Math.abs(delta))} maior no pior distrito`
            : "Sem mudança no pior distrito"}
      </p>
    </section>
  );
}
