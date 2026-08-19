"""Public namespace contract for the frozen City OS C0 surface."""

from __future__ import annotations

import city_os.contracts as contracts
from city_os.contracts.api import (
    AmbulanceSnapshot,
    AmbulanceStatus,
    ApiError,
    BootstrapResponse,
    CallPriority,
    CallSnapshot,
    CallStatus,
    FleetSizeBounds,
    MethodologyMetadata,
    PairedMetrics,
    ScenarioObservation,
    ScenarioParseRequest,
    ScenarioParseResponse,
    ScenarioSource,
    ScenarioType,
    SimulationCreatedResponse,
    SimulationFrame,
    SimulationJobResponse,
    SimulationJobStatus,
    SimulationMetrics,
    SimulationPolicy,
    SimulationRequest,
)
from city_os.contracts.artifacts import (
    ArtifactChecksum,
    ArtifactEntry,
    ArtifactManifest,
    CameraObservation,
    EdgeState,
    H3Density,
    RoadEdge,
    RoadNode,
)
from city_os.contracts.export_schema import export_contracts

REQUIRED_EXPORTS = {
    "AmbulanceSnapshot": AmbulanceSnapshot,
    "AmbulanceStatus": AmbulanceStatus,
    "ApiError": ApiError,
    "ArtifactChecksum": ArtifactChecksum,
    "ArtifactEntry": ArtifactEntry,
    "ArtifactManifest": ArtifactManifest,
    "BootstrapResponse": BootstrapResponse,
    "CallPriority": CallPriority,
    "CallSnapshot": CallSnapshot,
    "CallStatus": CallStatus,
    "CameraObservation": CameraObservation,
    "EdgeState": EdgeState,
    "FleetSizeBounds": FleetSizeBounds,
    "H3Density": H3Density,
    "MethodologyMetadata": MethodologyMetadata,
    "PairedMetrics": PairedMetrics,
    "RoadEdge": RoadEdge,
    "RoadNode": RoadNode,
    "ScenarioObservation": ScenarioObservation,
    "ScenarioParseRequest": ScenarioParseRequest,
    "ScenarioParseResponse": ScenarioParseResponse,
    "ScenarioSource": ScenarioSource,
    "ScenarioType": ScenarioType,
    "SimulationCreatedResponse": SimulationCreatedResponse,
    "SimulationFrame": SimulationFrame,
    "SimulationJobResponse": SimulationJobResponse,
    "SimulationJobStatus": SimulationJobStatus,
    "SimulationMetrics": SimulationMetrics,
    "SimulationPolicy": SimulationPolicy,
    "SimulationRequest": SimulationRequest,
    "export_contracts": export_contracts,
}


def test_contracts_namespace_reexports_every_frozen_contract_and_exporter() -> None:
    """Removing a root re-export makes downstream consumers import private modules."""
    for name, expected in REQUIRED_EXPORTS.items():
        assert getattr(contracts, name) is expected


def test_contracts_all_is_duplicate_free_and_covers_frozen_contract_names() -> None:
    """Omitting or duplicating public names makes star imports incomplete or ambiguous."""
    assert len(contracts.__all__) == len(set(contracts.__all__))
    assert REQUIRED_EXPORTS.keys() <= set(contracts.__all__)
