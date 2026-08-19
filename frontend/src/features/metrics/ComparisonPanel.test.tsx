import { render, screen, within } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import type { SimulationMetrics } from "../../lib/contracts/generated";
import { ComparisonPanel } from "./ComparisonPanel";

function metric(
  policy: "baseline" | "optimized",
  p90: number,
  overrides: Partial<SimulationMetrics> = {},
): SimulationMetrics {
  return {
    policy,
    mean_seconds: 720,
    p50_seconds: 660,
    p90_seconds: p90,
    p95_seconds: 1_500,
    within_8m_pct: 32,
    within_12m_pct: 58,
    within_20m_pct: 87,
    worst_district_p90_seconds: 1_560,
    queued_calls: 3,
    unserved_calls: 1,
    reposition_km: 0,
    ...overrides,
  };
}

describe("ComparisonPanel", () => {
  it("formats the exact primary p90 improvement", () => {
    render(
      <ComparisonPanel
        baseline={metric("baseline", 1_260)}
        optimized={metric("optimized", 840, { reposition_km: 24.5 })}
      />,
    );

    expect(screen.getByText("21.0 min")).toBeInTheDocument();
    expect(screen.getByText("14.0 min")).toBeInTheDocument();
    expect(screen.getByText("−7.0 min")).toBeInTheDocument();
    expect(screen.getByText("33.3% faster")).toBeInTheDocument();
    expect(screen.getByLabelText("Variação do P90").querySelector("[data-tone='positive']")).not.toBeNull();
  });

  it("shows pending and partial states without inventing a comparison", () => {
    const { rerender } = render(<ComparisonPanel />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Execute a simulação para comparar as políticas.",
    );
    expect(screen.getAllByText("Aguardando dados")).toHaveLength(2);

    rerender(<ComparisonPanel baseline={metric("baseline", 1_260)} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Comparação parcial: aguardando a outra política.",
    );
    expect(screen.queryByLabelText("Variação do P90")).not.toBeInTheDocument();
  });

  it("treats equal outcomes as neutral", () => {
    render(
      <ComparisonPanel
        baseline={metric("baseline", 900)}
        optimized={metric("optimized", 900)}
      />,
    );

    const outcome = screen.getByLabelText("Variação do P90");
    expect(within(outcome).getByText("0.0 min")).toBeInTheDocument();
    expect(within(outcome).getByText("No change")).toBeInTheDocument();
    expect(outcome.querySelector("[data-tone='neutral']")).not.toBeNull();
  });

  it("labels a worse outcome as negative rather than an improvement", () => {
    render(
      <ComparisonPanel
        baseline={metric("baseline", 840)}
        optimized={metric("optimized", 1_260)}
      />,
    );

    const outcome = screen.getByLabelText("Variação do P90");
    expect(within(outcome).getByText("+7.0 min")).toBeInTheDocument();
    expect(within(outcome).getByText("50.0% slower")).toBeInTheDocument();
    expect(outcome.querySelector("[data-tone='negative']")).not.toBeNull();
    expect(outcome.querySelector("[data-tone='positive']")).toBeNull();
  });

  it("keeps operational cost, service levels, equity and source visible", () => {
    render(
      <ComparisonPanel
        baseline={metric("baseline", 1_260, { worst_district_p90_seconds: 1_800 })}
        optimized={metric("optimized", 840, {
          worst_district_p90_seconds: 1_200,
          reposition_km: 24.5,
          within_8m_pct: 48,
        })}
        confidenceNote="Comparação pareada, seed 42."
        sourceNote="Geometria real; fluxo inferido; chamadas sintéticas."
      />,
    );

    expect(screen.getByText("24.5 km")).toBeInTheDocument();
    expect(screen.getByText(/32.0% → 48.0%/)).toBeInTheDocument();
    expect(screen.getByText("P90 do distrito mais crítico")).toBeInTheDocument();
    expect(screen.getByText("Comparação pareada, seed 42.")).toBeInTheDocument();
    expect(
      screen.getByText("Geometria real; fluxo inferido; chamadas sintéticas."),
    ).toBeInTheDocument();
  });
});
