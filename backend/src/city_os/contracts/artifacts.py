"""Strict, versioned contracts for City OS spatial and sensor artifacts."""

import base64
import binascii
from datetime import datetime
from typing import Annotated, Literal

import h3  # type: ignore[import-untyped]
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StringConstraints,
    WithJsonSchema,
    field_validator,
    model_validator,
)
from shapely import from_wkb  # type: ignore[import-untyped]
from shapely.errors import GEOSException  # type: ignore[import-untyped]


class StrictModel(BaseModel):
    """Base model that prevents silent producer-contract drift."""

    model_config = ConfigDict(extra="forbid", strict=True)


NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveFiniteFloat = Annotated[FiniteFloat, Field(gt=0)]
NonNegativeFiniteFloat = Annotated[FiniteFloat, Field(ge=0)]
Confidence = Annotated[FiniteFloat, Field(ge=0, le=1)]
Longitude = Annotated[FiniteFloat, Field(ge=-180, le=180)]
Latitude = Annotated[FiniteFloat, Field(ge=-90, le=90)]
Sha256Value = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
H3Cell = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{15}$", strict=True)]
NonEmptyText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)
]
RelativePosixPath = Annotated[
    str,
    StringConstraints(min_length=1, strict=True),
    WithJsonSchema(
        {
            "type": "string",
            "minLength": 1,
            "pattern": r"^(?!/)(?!.*\\)(?!.*(?:^|/)(?:\.|\.\.)(?:/|$))(?!.*//).+$",
        }
    ),
]
Base64Wkb = Annotated[
    str,
    StringConstraints(min_length=1, strict=True),
    WithJsonSchema({"type": "string", "minLength": 1, "contentEncoding": "base64"}),
]


def _validate_h3_resolution_eight(value: str) -> str:
    if not h3.is_valid_cell(value) or h3.get_resolution(value) != 8:
        raise ValueError("must be a valid H3 resolution 8 cell")
    return value


def _validate_bucket_start(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("must be timezone-aware")
    if value.minute % 5 != 0 or value.second != 0 or value.microsecond != 0:
        raise ValueError("must align to a five-minute boundary")
    return value


def _validate_nonempty_text(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty")
    return value


class RoadNode(StrictModel):
    """A directed-road-network node located in WGS84 coordinates."""

    node_id: NonNegativeInt
    x: Longitude
    y: Latitude
    h3_cell: H3Cell

    @field_validator("h3_cell")
    @classmethod
    def validate_h3_cell(cls, value: str) -> str:
        return _validate_h3_resolution_eight(value)


class RoadEdge(StrictModel):
    """A directed road segment and its baseline travel characteristics."""

    edge_id: NonNegativeInt
    u: NonNegativeInt
    v: NonNegativeInt
    length_m: PositiveFiniteFloat
    free_flow_seconds: PositiveFiniteFloat
    capacity_vph: NonNegativeFiniteFloat
    geometry_wkb: Base64Wkb

    @field_validator("geometry_wkb")
    @classmethod
    def validate_geometry_wkb(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        try:
            geometry_wkb = base64.b64decode(value.encode("ascii"), validate=True)
            from_wkb(geometry_wkb)
        except (UnicodeEncodeError, ValueError, binascii.Error, GEOSException) as error:
            raise ValueError("must be valid base64-encoded WKB") from error
        return value


class CameraObservation(StrictModel):
    """An aggregated, privacy-safe camera count for one edge and time bucket."""

    camera_id: NonEmptyText
    edge_id: NonNegativeInt
    bucket_start: datetime
    object_class: NonEmptyText
    direction: NonEmptyText
    count: NonNegativeInt
    confidence: Confidence

    @field_validator("camera_id", "object_class", "direction")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_nonempty_text(value)

    @field_validator("bucket_start")
    @classmethod
    def validate_bucket_start(cls, value: datetime) -> datetime:
        return _validate_bucket_start(value)


class EdgeState(StrictModel):
    """A flow-derived state for one directed edge and time bucket."""

    edge_id: NonNegativeInt
    bucket_start: datetime
    flow_vph: NonNegativeFiniteFloat
    speed_kph: NonNegativeFiniteFloat
    travel_seconds: NonNegativeFiniteFloat
    occupancy_people: NonNegativeFiniteFloat
    confidence: Confidence

    @field_validator("bucket_start")
    @classmethod
    def validate_bucket_start(cls, value: datetime) -> datetime:
        return _validate_bucket_start(value)


class H3Density(StrictModel):
    """An H3-cell density estimate for a five-minute observation bucket."""

    cell: H3Cell
    bucket_start: datetime
    density_people_km2: NonNegativeFiniteFloat
    emergency_intensity_hour: NonNegativeFiniteFloat
    confidence: Confidence

    @field_validator("cell")
    @classmethod
    def validate_cell(cls, value: str) -> str:
        return _validate_h3_resolution_eight(value)

    @field_validator("bucket_start")
    @classmethod
    def validate_bucket_start(cls, value: datetime) -> datetime:
        return _validate_bucket_start(value)


class ArtifactChecksum(StrictModel):
    """The immutable checksum of a manifest-listed artifact."""

    algorithm: Literal["sha256"]
    value: Sha256Value


class ArtifactEntry(StrictModel):
    """A single local artifact listed in a versioned artifact manifest."""

    name: NonEmptyText
    path: RelativePosixPath
    media_type: NonEmptyText
    checksum: ArtifactChecksum

    @field_validator("name", "media_type")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_nonempty_text(value)

    @field_validator("path")
    @classmethod
    def validate_relative_posix_path(cls, value: str) -> str:
        if not value or value.startswith("/") or "\\" in value:
            raise ValueError("must be a relative POSIX path")
        if any(segment in {"", ".", ".."} for segment in value.split("/")):
            raise ValueError("must not contain empty, dot, or dotdot path segments")
        return value


class ArtifactManifest(StrictModel):
    """A deterministic list of checksum-addressed local artifacts."""

    schema_version: Literal["1.0"]
    artifacts: Annotated[tuple[ArtifactEntry, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_unique_artifacts(self) -> "ArtifactManifest":
        names = [artifact.name for artifact in self.artifacts]
        paths = [artifact.path for artifact in self.artifacts]
        if len(names) != len(set(names)):
            raise ValueError("artifact names must be unique")
        if len(paths) != len(set(paths)):
            raise ValueError("artifact paths must be unique")
        return self
