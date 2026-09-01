"""Add cables, tubes, individual fibers and splice connections.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def audit_constraints() -> list[sa.ForeignKeyConstraint]:
    return [
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="RESTRICT"),
    ]


def upgrade() -> None:
    op.create_table(
        "optical_cable",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("network_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("map_feature_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("cable_class", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="planned"),
        sa.Column("fiber_count", sa.Integer(), nullable=False),
        sa.Column("tube_count", sa.Integer(), nullable=False),
        sa.Column("fibers_per_tube", sa.Integer(), nullable=False),
        sa.Column("measured_length_m", sa.Float(), nullable=True),
        sa.Column("technical_reserve_m", sa.Float(), nullable=False, server_default="0"),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *audit_columns(),
        sa.CheckConstraint(
            "cable_class IN ('feeder', 'distribution', 'branch', 'drop')",
            name="ck_optical_cable_class",
        ),
        sa.CheckConstraint("fiber_count > 0", name="ck_optical_cable_fiber_count"),
        sa.CheckConstraint("tube_count > 0", name="ck_optical_cable_tube_count"),
        sa.CheckConstraint("fibers_per_tube > 0", name="ck_optical_cable_fibers_per_tube"),
        sa.ForeignKeyConstraint(["network_id"], ["service_network.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["map_feature_id"], ["map_feature.id"], ondelete="SET NULL"),
        *audit_constraints(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("map_feature_id", name="uq_optical_cable_map_feature"),
    )
    op.create_index("ix_optical_cable_network_id", "optical_cable", ["network_id"])
    op.create_index("ix_optical_cable_status", "optical_cable", ["status"])

    op.create_table(
        "cable_tube",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cable_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("color_code", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("position > 0", name="ck_cable_tube_position"),
        sa.ForeignKeyConstraint(["cable_id"], ["optical_cable.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cable_id", "position", name="uq_cable_tube_position"),
    )
    op.create_index("ix_cable_tube_cable_id", "cable_tube", ["cable_id"])

    op.create_table(
        "optical_fiber",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cable_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tube_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("global_position", sa.Integer(), nullable=False),
        sa.Column("color_code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="available"),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *audit_columns(),
        sa.CheckConstraint("position > 0", name="ck_optical_fiber_position"),
        sa.CheckConstraint("global_position > 0", name="ck_optical_fiber_global_position"),
        sa.CheckConstraint(
            "status IN ('available', 'reserved', 'occupied', 'damaged', 'deactivated')",
            name="ck_optical_fiber_status",
        ),
        sa.ForeignKeyConstraint(["cable_id"], ["optical_cable.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tube_id"], ["cable_tube.id"], ondelete="CASCADE"),
        *audit_constraints(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cable_id", "global_position", name="uq_optical_fiber_global_position"),
        sa.UniqueConstraint("tube_id", "position", name="uq_optical_fiber_tube_position"),
    )
    op.create_index("ix_optical_fiber_cable_id", "optical_fiber", ["cable_id"])
    op.create_index("ix_optical_fiber_tube_id", "optical_fiber", ["tube_id"])
    op.create_index("ix_optical_fiber_status", "optical_fiber", ["status"])

    op.create_table(
        "fiber_connection",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enclosure_feature_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_type", sa.String(length=32), nullable=False, server_default="fusion"),
        sa.Column("loss_db", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("notes", sa.String(length=500), nullable=True),
        *audit_columns(),
        sa.CheckConstraint(
            "connection_type IN ('fusion', 'connector', 'termination')",
            name="ck_fiber_connection_type",
        ),
        sa.CheckConstraint("loss_db >= 0", name="ck_fiber_connection_loss"),
        sa.ForeignKeyConstraint(["enclosure_feature_id"], ["map_feature.id"], ondelete="RESTRICT"),
        *audit_constraints(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fiber_connection_enclosure", "fiber_connection", ["enclosure_feature_id"])

    op.create_table(
        "fiber_connection_endpoint",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fiber_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("end_side", sa.String(length=1), nullable=False),
        sa.Column("role", sa.String(length=1), nullable=False),
        sa.CheckConstraint("end_side IN ('a', 'b')", name="ck_fiber_endpoint_side"),
        sa.CheckConstraint("role IN ('a', 'b')", name="ck_fiber_endpoint_role"),
        sa.ForeignKeyConstraint(["connection_id"], ["fiber_connection.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fiber_id"], ["optical_fiber.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id", "role", name="uq_fiber_endpoint_connection_role"),
        sa.UniqueConstraint("fiber_id", "end_side", name="uq_fiber_endpoint_usage"),
    )
    op.create_index(
        "ix_fiber_connection_endpoint_connection",
        "fiber_connection_endpoint",
        ["connection_id"],
    )
    op.create_index("ix_fiber_connection_endpoint_fiber", "fiber_connection_endpoint", ["fiber_id"])


def downgrade() -> None:
    op.drop_index("ix_fiber_connection_endpoint_fiber", table_name="fiber_connection_endpoint")
    op.drop_index("ix_fiber_connection_endpoint_connection", table_name="fiber_connection_endpoint")
    op.drop_table("fiber_connection_endpoint")
    op.drop_index("ix_fiber_connection_enclosure", table_name="fiber_connection")
    op.drop_table("fiber_connection")
    op.drop_index("ix_optical_fiber_status", table_name="optical_fiber")
    op.drop_index("ix_optical_fiber_tube_id", table_name="optical_fiber")
    op.drop_index("ix_optical_fiber_cable_id", table_name="optical_fiber")
    op.drop_table("optical_fiber")
    op.drop_index("ix_cable_tube_cable_id", table_name="cable_tube")
    op.drop_table("cable_tube")
    op.drop_index("ix_optical_cable_status", table_name="optical_cable")
    op.drop_index("ix_optical_cable_network_id", table_name="optical_cable")
    op.drop_table("optical_cable")
