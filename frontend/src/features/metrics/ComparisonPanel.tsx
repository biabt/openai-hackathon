import React from "react";

import type { SimulationMetrics } from "../../lib/contracts/generated";
import { EquityPanel } from "./EquityPanel";
import { MetricCard, type MetricTone } from "./MetricCard";

export interface ComparisonPanelProps {
  baseline?: SimulationMetrics | null;
  optimized?: SimulationMetrics | null;
  sourceNote?: string;
  confidenceNote?: string;
}

export function formatMinutes(seconds: number | null): string {
  return seconds == null ? "Sem dados" : `${(seconds / 60).toFixed(1)} min`;
}

function formatPercentage(value: number | null): string {
  return value == null ? "Sem dados" : `${value.toFixed(1)}%`;
}

function signedMinutes(seconds: number): string {
  if (seconds === 0) return "0.0 min";
  return `${seconds < 0 ? "−" : "+"}${formatMinutes(Math.abs(seconds))}`;
}

function Outcome({ baseline, optimized }: RequiredMetrics) {
  if (baseline.p90_seconds == null || optimized.p90_seconds == null) {
    return <p className="comparison-panel__pending">P90 ainda indisponível para comparação.</p>;
  }
  const savedSeconds = baseline.p90_seconds - optimized.p90_seconds;
  const relative =
    baseline.p90_seconds === 0 ? 0 : (savedSeconds / baseline.p90_seconds) * 100;
  const tone: MetricTone = savedSeconds > 0 ? "positive" : savedSeconds < 0 ? "negative" : "neutral";
  const label =
    savedSeconds > 0
      ? `${formatPercentage(relative)} faster`
      : savedSeconds < 0
        ? baseline.p90_seconds === 0
          ? "Worse; percentage unavailable"
          : `${formatPercentage(Math.abs(relative))} slower`
        : "No change";

  return (
    <div className="comparison-panel__outcome" aria-label="Variação do P90">
      <MetricCard
        label="Diferença"
        value={signedMinutes(optimized.p90_seconds - baseline.p90_seconds)}
        detail={label}
        tone={tone}
        prominent
      />
    </div>
  );
}

interface RequiredMetrics {
  baseline: SimulationMetrics;
  optimized: SimulationMetrics;
}

function ServiceLevels({ baseline, optimized }: RequiredMetrics) {
  const levels = [
    ["até 8 min", baseline.within_8m_pct, optimized.within_8m_pct],
    ["até 12 min", baseline.within_12m_pct, optimized.within_12m_pct],
    ["até 20 min", baseline.within_20m_pct, optimized.within_20m_pct],
  ] as const;

  return (
    <section aria-labelledby="service-level-title">
      <h3 id="service-level-title">Chamados atendidos</h3>
      <div className="comparison-panel__chips">
        {levels.map(([label, before, after]) => (
          <span className="service-chip" key={label}>
            <strong>{label}</strong> {formatPercentage(before)} → {formatPercentage(after)}
          </span>
        ))}
      </div>
    </section>
  );
}

function SecondaryMetrics({ baseline, optimized }: RequiredMetrics) {
  const rows = [
    ["Média", baseline.mean_seconds, optimized.mean_seconds, "time"],
    ["P50", baseline.p50_seconds, optimized.p50_seconds, "time"],
    ["P95", baseline.p95_seconds, optimized.p95_seconds, "time"],
    ["Reposicionamento", baseline.reposition_km, optimized.reposition_km, "distance"],
  ] as const;

  return (
    <table className="comparison-panel__table">
      <caption>Contexto operacional</caption>
      <thead>
        <tr>
          <th scope="col">Métrica</th>
          <th scope="col">Antes</th>
          <th scope="col">Depois</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([label, before, after, kind]) => (
          <tr key={label}>
            <th scope="row">{label}</th>
            <td>{kind === "time" ? formatMinutes(before) : `${before?.toFixed(1) ?? "Sem dados"} km`}</td>
            <td>{kind === "time" ? formatMinutes(after) : `${after?.toFixed(1) ?? "Sem dados"} km`}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ComparisonPanel({
  baseline,
  optimized,
  sourceNote = "Geometria real; fluxo inferido; chamadas sintéticas.",
  confidenceNote = "Mesma chamada, frota e condições nas duas políticas.",
}: ComparisonPanelProps) {
  const hasBaseline = baseline != null;
  const hasOptimized = optimized != null;

  return (
    <aside aria-labelledby="comparison-title" className="comparison-panel">
      <header>
        <p className="eyebrow">Tempo de resposta</p>
        <h2 id="comparison-title">Antes × Depois</h2>
      </header>

      <div className="comparison-panel__primary">
        <MetricCard
          label="Antes · política estática · P90"
          value={hasBaseline ? formatMinutes(baseline.p90_seconds) : "Aguardando dados"}
          prominent
        />
        <MetricCard
          label="Depois · política preditiva · P90"
          value={hasOptimized ? formatMinutes(optimized.p90_seconds) : "Aguardando dados"}
          prominent
        />
      </div>

      {hasBaseline && hasOptimized ? (
        <>
          <Outcome baseline={baseline} optimized={optimized} />
          <ServiceLevels baseline={baseline} optimized={optimized} />
          <SecondaryMetrics baseline={baseline} optimized={optimized} />
          <EquityPanel baseline={baseline} optimized={optimized} />
          <p className="comparison-panel__queue">
            Fila: {baseline.queued_calls} → {optimized.queued_calls} · Não atendidos:{" "}
            {baseline.unserved_calls} → {optimized.unserved_calls}
          </p>
        </>
      ) : (
        <p role="status" className="comparison-panel__pending">
          {hasBaseline || hasOptimized
            ? "Comparação parcial: aguardando a outra política."
            : "Execute a simulação para comparar as políticas."}
        </p>
      )}

      <footer>
        <p>{confidenceNote}</p>
        <p>{sourceNote}</p>
      </footer>
    </aside>
  );
}
