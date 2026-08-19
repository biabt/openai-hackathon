"""Deterministic ambulance placement policies."""

from .baseline import static_p_median
from .cvar import OptimizationConfig, optimize_positions
from .reposition import Allocation, AmbulanceSnapshot, DemandPoint, FleetSnapshot

__all__ = [
    "Allocation",
    "AmbulanceSnapshot",
    "DemandPoint",
    "FleetSnapshot",
    "OptimizationConfig",
    "optimize_positions",
    "static_p_median",
]
