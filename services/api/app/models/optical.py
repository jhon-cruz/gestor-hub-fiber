"""Explicit optical equipment and port-capacity domain models."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OpticalDeviceType(StrEnum):
    OLT = "olt"
    DIO = "dio"
    SPLITTER = "splitter"
    CTO = "cto"


class OpticalPortKind(StrEnum):
    PON = "pon"
    ADAPTER = "adapter"
    SPLITTER_INPUT = "splitter_input"
    SPLITTER_OUTPUT = "splitter_output"
    CTO_DISTRIBUTION = "cto_distribution"


class OpticalPortStatus(StrEnum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    OCCUPIED = "occupied"
    DAMAGED = "damaged"
    DEACTIVATED = "deactivated"


class OpticalDevice(Base):
    __tablename__ = "optical_device"
    __table_args__ = (
        CheckConstraint(
            "device_type IN ('olt', 'dio', 'splitter', 'cto')",
            name="ck_optical_device_type",
        ),
        CheckConstraint("port_capacity > 0", name="ck_optical_device_port_capacity"),
        UniqueConstraint("map_feature_id", name="uq_optical_device_map_feature"),
        Index("ix_optical_device_device_type", "device_type"),
        Index("ix_optical_device_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    map_feature_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("map_feature.id", ondelete="SET NULL"),
        nullable=True,
    )
    device_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")
    manufacturer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    port_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    ports: Mapped[list[OpticalPort]] = relationship(
        back_populates="device", cascade="all, delete-orphan", passive_deletes=True
    )


class OpticalPort(Base):
    __tablename__ = "optical_port"
    __table_args__ = (
        CheckConstraint(
            "port_kind IN ('pon', 'adapter', 'splitter_input', 'splitter_output', "
            "'cto_distribution')",
            name="ck_optical_port_kind",
        ),
        CheckConstraint("position > 0", name="ck_optical_port_position"),
        CheckConstraint(
            "status IN ('available', 'reserved', 'occupied', 'damaged', 'deactivated')",
            name="ck_optical_port_status",
        ),
        UniqueConstraint("device_id", "port_kind", "position", name="uq_optical_port_position"),
        Index("ix_optical_port_device_id", "device_id"),
        Index("ix_optical_port_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("optical_device.id", ondelete="CASCADE"), nullable=False
    )
    port_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="available")
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    device: Mapped[OpticalDevice] = relationship(back_populates="ports")
