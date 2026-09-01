"""Relational cable, tube, fiber and splice topology."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
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


class OpticalCable(Base):
    __tablename__ = "optical_cable"
    __table_args__ = (
        CheckConstraint(
            "cable_class IN ('feeder', 'distribution', 'branch', 'drop')",
            name="ck_optical_cable_class",
        ),
        CheckConstraint("fiber_count > 0", name="ck_optical_cable_fiber_count"),
        CheckConstraint("tube_count > 0", name="ck_optical_cable_tube_count"),
        CheckConstraint("fibers_per_tube > 0", name="ck_optical_cable_fibers_per_tube"),
        UniqueConstraint("map_feature_id", name="uq_optical_cable_map_feature"),
        Index("ix_optical_cable_network_id", "network_id"),
        Index("ix_optical_cable_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    network_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_network.id", ondelete="SET NULL"), nullable=True
    )
    map_feature_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("map_feature.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    cable_class: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")
    fiber_count: Mapped[int] = mapped_column(Integer, nullable=False)
    tube_count: Mapped[int] = mapped_column(Integer, nullable=False)
    fibers_per_tube: Mapped[int] = mapped_column(Integer, nullable=False)
    measured_length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    technical_reserve_m: Mapped[float] = mapped_column(Float, nullable=False, default=0)
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
    tubes: Mapped[list[CableTube]] = relationship(
        back_populates="cable", cascade="all, delete-orphan", passive_deletes=True
    )
    fibers: Mapped[list[OpticalFiber]] = relationship(
        back_populates="cable", cascade="all, delete-orphan", passive_deletes=True
    )


class CableTube(Base):
    __tablename__ = "cable_tube"
    __table_args__ = (
        CheckConstraint("position > 0", name="ck_cable_tube_position"),
        UniqueConstraint("cable_id", "position", name="uq_cable_tube_position"),
        Index("ix_cable_tube_cable_id", "cable_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cable_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("optical_cable.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    color_code: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    cable: Mapped[OpticalCable] = relationship(back_populates="tubes")
    fibers: Mapped[list[OpticalFiber]] = relationship(back_populates="tube")


class OpticalFiber(Base):
    __tablename__ = "optical_fiber"
    __table_args__ = (
        CheckConstraint("position > 0", name="ck_optical_fiber_position"),
        CheckConstraint("global_position > 0", name="ck_optical_fiber_global_position"),
        CheckConstraint(
            "status IN ('available', 'reserved', 'occupied', 'damaged', 'deactivated')",
            name="ck_optical_fiber_status",
        ),
        UniqueConstraint("cable_id", "global_position", name="uq_optical_fiber_global_position"),
        UniqueConstraint("tube_id", "position", name="uq_optical_fiber_tube_position"),
        Index("ix_optical_fiber_cable_id", "cable_id"),
        Index("ix_optical_fiber_tube_id", "tube_id"),
        Index("ix_optical_fiber_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cable_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("optical_cable.id", ondelete="CASCADE"), nullable=False
    )
    tube_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cable_tube.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    global_position: Mapped[int] = mapped_column(Integer, nullable=False)
    color_code: Mapped[str] = mapped_column(String(32), nullable=False)
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
    cable: Mapped[OpticalCable] = relationship(back_populates="fibers")
    tube: Mapped[CableTube] = relationship(back_populates="fibers")
    endpoints: Mapped[list[FiberConnectionEndpoint]] = relationship(
        back_populates="fiber", passive_deletes=True
    )


class FiberConnection(Base):
    __tablename__ = "fiber_connection"
    __table_args__ = (
        CheckConstraint(
            "connection_type IN ('fusion', 'connector', 'termination')",
            name="ck_fiber_connection_type",
        ),
        CheckConstraint("loss_db >= 0", name="ck_fiber_connection_loss"),
        Index("ix_fiber_connection_enclosure", "enclosure_feature_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enclosure_feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("map_feature.id", ondelete="RESTRICT"), nullable=False
    )
    connection_type: Mapped[str] = mapped_column(String(32), nullable=False, default="fusion")
    loss_db: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
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
    endpoints: Mapped[list[FiberConnectionEndpoint]] = relationship(
        back_populates="connection", cascade="all, delete-orphan", passive_deletes=True
    )


class FiberConnectionEndpoint(Base):
    __tablename__ = "fiber_connection_endpoint"
    __table_args__ = (
        CheckConstraint("end_side IN ('a', 'b')", name="ck_fiber_endpoint_side"),
        CheckConstraint("role IN ('a', 'b')", name="ck_fiber_endpoint_role"),
        UniqueConstraint("connection_id", "role", name="uq_fiber_endpoint_connection_role"),
        UniqueConstraint("fiber_id", "end_side", name="uq_fiber_endpoint_usage"),
        Index("ix_fiber_connection_endpoint_connection", "connection_id"),
        Index("ix_fiber_connection_endpoint_fiber", "fiber_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fiber_connection.id", ondelete="CASCADE"), nullable=False
    )
    fiber_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("optical_fiber.id", ondelete="RESTRICT"), nullable=False
    )
    end_side: Mapped[str] = mapped_column(String(1), nullable=False)
    role: Mapped[str] = mapped_column(String(1), nullable=False)
    connection: Mapped[FiberConnection] = relationship(back_populates="endpoints")
    fiber: Mapped[OpticalFiber] = relationship(back_populates="endpoints")
