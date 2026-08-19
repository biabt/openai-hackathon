import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { formatSimulatedTime, PlaybackControls } from "./PlaybackControls";

describe("PlaybackControls", () => {
  it("runs, resets, toggles playback, changes speed and scrubs six hours", () => {
    const onRun = vi.fn();
    const onReset = vi.fn();
    const onPlayingChange = vi.fn();
    const onSpeedChange = vi.fn();
    const onScrub = vi.fn();

    render(
      <PlaybackControls
        currentMinute={90}
        playing={false}
        speed={1}
        job="running"
        onRun={onRun}
        onReset={onReset}
        onPlayingChange={onPlayingChange}
        onSpeedChange={onSpeedChange}
        onScrub={onScrub}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Executar" }));
    fireEvent.click(screen.getByRole("button", { name: "Reiniciar" }));
    fireEvent.click(screen.getByRole("button", { name: "Reproduzir" }));
    fireEvent.click(screen.getByRole("button", { name: "4×" }));
    fireEvent.change(screen.getByRole("slider", { name: "Tempo simulado" }), {
      target: { value: "360" },
    });

    expect(onRun).toHaveBeenCalledOnce();
    expect(onReset).toHaveBeenCalledOnce();
    expect(onPlayingChange).toHaveBeenCalledWith(true);
    expect(onSpeedChange).toHaveBeenCalledWith(4);
    expect(onScrub).toHaveBeenCalledWith(360);
    expect(screen.getByText("01:30 de 06:00")).toBeInTheDocument();
  });

  it("announces formatted simulated time", () => {
    expect(formatSimulatedTime(0)).toBe("00:00");
    expect(formatSimulatedTime(359)).toBe("05:59");
  });

  it("surfaces transport failures", () => {
    render(
      <PlaybackControls
        currentMinute={10}
        playing={false}
        speed={1}
        job="failed"
        connection="disconnected"
        error="A conexão foi interrompida"
        onRun={vi.fn()}
        onReset={vi.fn()}
        onPlayingChange={vi.fn()}
        onSpeedChange={vi.fn()}
        onScrub={vi.fn()}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("A conexão foi interrompida");
  });
});
