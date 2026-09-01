"""Validated cable, fiber and connection inputs."""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

CableClass = Literal["feeder", "distribution", "branch", "drop"]
OperationalStatus = Literal[
    "planned", "under_construction", "active", "reserved", "damaged", "deactivated"
]
FiberStatus = Literal["available", "reserved", "occupied", "damaged", "deactivated"]
ConnectionType = Literal["fusion", "connector", "termination"]
EndSide = Literal["a", "b"]


class OpticalCableCreate(BaseModel):
    network_id: uuid.UUID | None = None
    map_feature_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=160)
    cable_class: CableClass
    status: OperationalStatus = "planned"
    fiber_count: int = Field(ge=1, le=6912)
    tube_count: int = Field(ge=1, le=576)
    fibers_per_tube: int = Field(ge=1, le=48)
    measured_length_m: float | None = Field(default=None, ge=0)
    technical_reserve_m: float = Field(default=0, ge=0)
    properties: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_capacity(self):
        if self.tube_count * self.fibers_per_tube < self.fiber_count:
            raise ValueError("tube capacity is smaller than fiber count")
        return self


class OpticalCableUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    cable_class: CableClass | None = None
    status: OperationalStatus | None = None
    measured_length_m: float | None = Field(default=None, ge=0)
    technical_reserve_m: float | None = Field(default=None, ge=0)
    properties: dict[str, Any] | None = None
    expected_revision: int = Field(ge=1)


class OpticalFiberUpdate(BaseModel):
    status: FiberStatus | None = None
    properties: dict[str, Any] | None = None
    expected_revision: int = Field(ge=1)


class ConnectionEndpointInput(BaseModel):
    fiber_id: uuid.UUID
    end_side: EndSide


class FiberConnectionCreate(BaseModel):
    enclosure_feature_id: uuid.UUID
    connection_type: ConnectionType = "fusion"
    loss_db: float = Field(default=0.1, ge=0, le=10)
    notes: str | None = Field(default=None, max_length=500)
    endpoints: list[ConnectionEndpointInput] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_distinct_endpoints(self):
        keys = {(item.fiber_id, item.end_side) for item in self.endpoints}
        if len(keys) != 2:
            raise ValueError("connection endpoints must be distinct")
        if self.endpoints[0].fiber_id == self.endpoints[1].fiber_id:
            raise ValueError("a fiber cannot be connected to itself")
        return self


class FiberPortLinkCreate(BaseModel):
    fiber_id: uuid.UUID
    fiber_end: EndSide
    port_id: uuid.UUID
    port_side: EndSide = "a"
    insertion_loss_db: float = Field(default=0.2, ge=0, le=10)
    notes: str | None = Field(default=None, max_length=500)
