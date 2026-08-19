"use client";

import { type FormEvent, useState } from "react";
import type { CityOsTransport } from "@/lib/api/transport";
import type { ScenarioObservation } from "@/lib/contracts/generated";

export type SensorComposerProps = {
  transport: Pick<CityOsTransport, "parseScenarioCard">;
  onParsed: (observation: ScenarioObservation) => void;
  initialText?: string;
  fallbackObservation?: ScenarioObservation;
};

function observationSummary(observation: ScenarioObservation): string {
  const item = observation as ScenarioObservation & {
    type?: string;
    starts_at?: string;
    ends_at?: string;
    source?: string;
    confidence?: number;
  };
  const confidence = typeof item.confidence === "number"
    ? ` · confiança ${Math.round(item.confidence * 100)}%`
    : "";
  return `${item.type ?? "cenário"} · ${item.starts_at ?? "início definido"}–${item.ends_at ?? "fim definido"}${confidence}`;
}

export function SensorComposer({
  transport,
  onParsed,
  initialText = "",
  fallbackObservation,
}: SensorComposerProps) {
  const [text, setText] = useState(initialText);
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parsed, setParsed] = useState<ScenarioObservation | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!text.trim() || parsing) return;
    setParsing(true);
    setError(null);
    try {
      const observation = await transport.parseScenarioCard(text.trim());
      setParsed(observation);
      onParsed(observation);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "A observação não pôde ser interpretada.";
      setError(fallbackObservation
        ? `${message} O card local armazenado foi usado como fallback determinístico.`
        : message);
      setParsed(fallbackObservation ?? null);
      if (fallbackObservation) onParsed(fallbackObservation);
    } finally {
      setParsing(false);
    }
  };

  return (
    <form className="sensor-composer" onSubmit={submit} aria-labelledby="sensor-composer-title">
      <div>
        <p className="eyebrow">Compositor determinístico</p>
        <h3 id="sensor-composer-title">Descrever uma observação</h3>
        <p>Entrada digitada para demonstração — sem monitoramento da internet em tempo real.</p>
      </div>
      <label htmlFor="sensor-message">Mensagem do sensor simulado</label>
      <textarea
        id="sensor-message"
        value={text}
        onChange={(event) => setText(event.target.value)}
        rows={3}
      />
      <button type="submit" disabled={!text.trim() || parsing}>
        {parsing ? "Interpretando…" : "Interpretar observação"}
      </button>
      {error ? <p className="sensor-composer__error" role="alert">Falha ao interpretar: {error}</p> : null}
      {parsed ? (
        <p className="sensor-composer__success" role="status">
          Observação validada: {observationSummary(parsed)} · fonte simulada
        </p>
      ) : null}
    </form>
  );
}
