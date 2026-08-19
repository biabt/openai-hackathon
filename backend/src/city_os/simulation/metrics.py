"""Response-time metrics used by simulation frames and terminal results."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

import numpy as np

from city_os.contracts import SimulationMetrics, SimulationPolicy


def compute_metrics(
    policy: SimulationPolicy,
    responses: Iterable[tuple[str, float]],
    *,
    queued_calls: int = 0,
    unserved_calls: int = 0,
    reposition_km: float = 0.0,
) -> SimulationMetrics:
    """Compute honest empirical metrics from ``(district, seconds)`` samples."""
    samples = [(district, float(seconds)) for district, seconds in responses]
    if not samples:
        return SimulationMetrics(
            policy=policy,
            mean_seconds=None,
            p50_seconds=None,
            p90_seconds=None,
            p95_seconds=None,
            within_8m_pct=None,
            within_12m_pct=None,
            within_20m_pct=None,
            worst_district_p90_seconds=None,
            queued_calls=queued_calls,
            unserved_calls=unserved_calls,
            reposition_km=float(reposition_km),
        )
    values = np.asarray([seconds for _, seconds in samples], dtype=float)
    districts: dict[str, list[float]] = defaultdict(list)
    for district, seconds in samples:
        districts[district].append(seconds)
    district_p90 = [float(np.percentile(group, 90)) for group in districts.values()]
    return SimulationMetrics(
        policy=policy,
        mean_seconds=float(np.mean(values)),
        p50_seconds=float(np.percentile(values, 50)),
        p90_seconds=float(np.percentile(values, 90)),
        p95_seconds=float(np.percentile(values, 95)),
        within_8m_pct=float(np.mean(values <= 480) * 100),
        within_12m_pct=float(np.mean(values <= 720) * 100),
        within_20m_pct=float(np.mean(values <= 1200) * 100),
        worst_district_p90_seconds=max(district_p90),
        queued_calls=queued_calls,
        unserved_calls=unserved_calls,
        reposition_km=float(reposition_km),
    )
