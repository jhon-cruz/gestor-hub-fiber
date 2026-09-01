"""Validated inputs for optical equipment and ports."""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

DeviceType = Literal["olt", "dio", "splitter", "cto"]
DeviceStatus = Literal[
    "planned", "under_construction", "active", "reserved", "damaged", "deactivated"
]
PortStatus = Literal["available", "reserved", "occupied", "damaged", "deactivated"]


class OpticalDeviceCreate(BaseModel):
    map_feature_id: uuid.UUID | None = None
    device_type: DeviceType
    name: str = Field(min_length=1, max_length=160)
    status: DeviceStatus = "planned"
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    port_capacity: int = Field(ge=1, le=4096)
    properties: dict[str, Any] = Field(default_factory=dict)


class OpticalDeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    status: DeviceStatus | None = None
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    properties: dict[str, Any] | None = None
    expected_revision: int = Field(ge=1)


class OpticalPortUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=120)
    status: PortStatus | None = None
    properties: dict[str, Any] | None = None
    expected_revision: int = Field(ge=1)
