"""Road travel-time functions."""

from __future__ import annotations

from typing import Any

import numpy as np


def bpr_travel_seconds(
    t0: Any,
    flow: Any,
    capacity: Any,
    alpha: float = 0.15,
    beta: float = 4.0,
    blocked: Any | None = None,
) -> np.ndarray | float:
    """Evaluate the BPR road cost, returning infinity for blocked edges.

    Inputs follow NumPy broadcasting. Scalar inputs return a Python ``float``;
    array-like inputs return an ndarray. Very large overload ratios saturate at
    the largest finite float unless an edge is explicitly blocked.
    """
    if not np.isfinite(alpha) or alpha < 0 or not np.isfinite(beta) or beta <= 0:
        raise ValueError("alpha must be non-negative and beta must be positive")
    base, volume, cap = np.broadcast_arrays(
        np.asarray(t0, dtype=float), np.asarray(flow, dtype=float), np.asarray(capacity, dtype=float)
    )
    if not np.all(np.isfinite(base)) or np.any(base < 0):
        raise ValueError("t0 must be finite and non-negative")
    if not np.all(np.isfinite(volume)) or np.any(volume < 0):
        raise ValueError("flow must be finite and non-negative")
    if not np.all(np.isfinite(cap)) or np.any(cap <= 0):
        raise ValueError("capacity must be finite and positive")
    maximum = np.finfo(float).max
    with np.errstate(over="ignore", invalid="ignore"):
        congestion = np.power(volume / cap, beta)
        travel = base * (1.0 + alpha * congestion)
    travel = np.where(base == 0, 0.0, travel)
    travel = np.minimum(np.nan_to_num(travel, nan=maximum, posinf=maximum), maximum)
    if blocked is not None:
        mask = np.broadcast_to(np.asarray(blocked, dtype=bool), travel.shape)
        travel = np.where(mask, np.inf, travel)
    return float(travel) if travel.ndim == 0 else travel
