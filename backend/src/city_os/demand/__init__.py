"""Seeded synthetic emergency demand."""

from .call_tape import CallEvent, generate_call_tape
from .profile import DemandProfile, DemandProfilePoint, load_demand_profile

__all__ = [
    "CallEvent",
    "DemandProfile",
    "DemandProfilePoint",
    "generate_call_tape",
    "load_demand_profile",
]
