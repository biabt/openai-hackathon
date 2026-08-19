import React from "react";

import type { ConnectionState, PlaybackSpeed, SimulationJobState } from "./state";

export interface PlaybackControlsProps {
  currentMinute: number;
  durationMinutes?: number;
  playing: boolean;
  speed: PlaybackSpeed;
  job?: SimulationJobState;
  connection?: ConnectionState;
  error?: string | null;
  disabled?: boolean;
  onRun: () => void;
  onReset: () => void;
  onPlayingChange: (playing: boolean) => void;
  onSpeedChange: (speed: PlaybackSpeed) => void;
  onScrub: (minute: number) => void;
}

export function formatSimulatedTime(minute: number): string {
  const safeMinute = Math.max(0, Math.round(minute));
  const hours = Math.floor(safeMinute / 60);
  const minutes = safeMinute % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

export function PlaybackControls({
  currentMinute,
  durationMinutes = 360,
  playing,
  speed,
  job = "idle",
  connection = "disconnected",
  error = null,
  disabled = false,
  onRun,
  onReset,
  onPlayingChange,
  onSpeedChange,
  onScrub,
}: PlaybackControlsProps) {
  const hasSimulation = job !== "idle" && job !== "creating";

  return (
    <section aria-label="Controles da simulação" className="playback-controls">
      <div className="playback-controls__actions">
        <button
          type="button"
          onClick={onRun}
          disabled={disabled || job === "creating"}
        >
          {job === "creating" ? "Iniciando…" : "Executar"}
        </button>
        <button type="button" onClick={onReset} disabled={disabled || !hasSimulation}>
          Reiniciar
        </button>
        <button
          type="button"
          onClick={() => onPlayingChange(!playing)}
          disabled={disabled || !hasSimulation || job === "failed"}
          aria-pressed={playing}
        >
          {playing ? "Pausar" : "Reproduzir"}
        </button>
      </div>

      <fieldset className="playback-controls__speed">
        <legend>Velocidade</legend>
        {([1, 2, 4] as const).map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={speed === value}
            onClick={() => onSpeedChange(value)}
            disabled={disabled}
          >
            {value}×
          </button>
        ))}
      </fieldset>

      <label className="playback-controls__timeline">
        <span>Tempo simulado</span>
        <input
          aria-label="Tempo simulado"
          type="range"
          min={0}
          max={durationMinutes}
          step={1}
          value={Math.round(currentMinute)}
          onChange={(event) => onScrub(Number(event.currentTarget.value))}
          disabled={disabled}
        />
      </label>
      <output aria-live="polite" aria-atomic="true">
        {formatSimulatedTime(currentMinute)} de {formatSimulatedTime(durationMinutes)}
      </output>
      <span className="playback-controls__connection" role="status">
        Conexão: {connection}
      </span>
      {error ? (
        <p className="playback-controls__error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
