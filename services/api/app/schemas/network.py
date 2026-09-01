"""Validated inputs for named geographic service networks."""

from typing import Any

from pydantic import BaseModel, Field, field_validator


def validate_viewport(value: list[float] | None) -> list[float] | None:
    if value is None:
        return None
    if len(value) != 4:
        raise ValueError("viewport must contain west, south, east and north")
    west, south, east, north = value
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("viewport coordinates are invalid")
    return value


class NetworkCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=1, max_length=80)
    country: str = Field(default="Brasil", min_length=1, max_length=80)
    viewport: list[float] | None = None
    source_namespace: str | None = Field(default=None, min_length=1, max_length=120)
    properties: dict[str, Any] = Field(default_factory=dict)

    _validate_viewport = field_validator("viewport")(validate_viewport)


class NetworkUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    state: str | None = Field(default=None, min_length=1, max_length=80)
    country: str | None = Field(default=None, min_length=1, max_length=80)
    viewport: list[float] | None = None
    properties: dict[str, Any] | None = None
    expected_revision: int = Field(ge=1)

    _validate_viewport = field_validator("viewport")(validate_viewport)


class NetworkAssign(BaseModel):
    source_namespace: str = Field(min_length=1, max_length=120)
