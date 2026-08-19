"""Deterministic paired ambulance simulation."""

from .engine import CallEvent, PairedResult, run_paired_simulation
from .metrics import compute_metrics

__all__ = ["CallEvent", "PairedResult", "compute_metrics", "run_paired_simulation"]
