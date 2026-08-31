"""GeoJSON-based schemas for the initial map endpoint."""

import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator

ALLOWED_STATUSES = {
    "planned",
    "under_construction",
    "active",
    "reserved",
    "damaged",
    "deactivated",
}


class MapFeatureCreate(BaseModel):
    fiberq_uuid: uuid.UUID | None = None
    feature_type: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    status: str = "planned"
    geometry: dict[str, Any]
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in ALLOWED_STATUSES:
            raise ValueError(f"unsupported status: {value}")
        return value

    @field_validator("geometry")
    @classmethod
    def validate_geojson(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value.get("type"), str) or "coordinates" not in value:
            raise ValueError("geometry must be a GeoJSON geometry object")
        return value


class MapFeatureUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    status: str | None = None
    geometry: dict[str, Any] | None = None
    properties: dict[str, Any] | None = None
    expected_revision: int = Field(ge=1)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is not None and value not in ALLOWED_STATUSES:
            raise ValueError(f"unsupported status: {value}")
        return value

    @field_validator("geometry")
    @classmethod
    def validate_geojson(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None and (
            not isinstance(value.get("type"), str) or "coordinates" not in value
        ):
            raise ValueError("geometry must be a GeoJSON geometry object")
        return value
