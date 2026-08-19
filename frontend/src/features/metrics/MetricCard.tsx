import React from "react";
import type { ReactNode } from "react";

export type MetricTone = "positive" | "negative" | "neutral";

export interface MetricCardProps {
  label: string;
  value: string;
  detail?: ReactNode;
  tone?: MetricTone;
  prominent?: boolean;
}

export function MetricCard({
  label,
  value,
  detail,
  tone = "neutral",
  prominent = false,
}: MetricCardProps) {
  const accent =
    tone === "positive" ? "#22a06b" : tone === "negative" ? "#d14343" : "currentColor";

  return (
    <article
      className={`metric-card metric-card--${tone}${prominent ? " metric-card--prominent" : ""}`}
      data-tone={tone}
      style={{ borderColor: accent }}
    >
      <p className="metric-card__label">{label}</p>
      <strong className="metric-card__value" style={{ color: accent }}>
        {value}
      </strong>
      {detail ? <div className="metric-card__detail">{detail}</div> : null}
    </article>
  );
}
