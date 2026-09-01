"""Add explicit optical devices and capacity-bound ports.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "optical_device",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("map_feature_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("device_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="planned"),
        sa.Column("manufacturer", sa.String(length=120), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("serial_number", sa.String(length=120), nullable=True),
        sa.Column("port_capacity", sa.Integer(), nullable=False),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "device_type IN ('olt', 'dio', 'splitter', 'cto')",
            name="ck_optical_device_type",
        ),
        sa.CheckConstraint("port_capacity > 0", name="ck_optical_device_port_capacity"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["map_feature_id"], ["map_feature.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("map_feature_id", name="uq_optical_device_map_feature"),
    )
    op.create_index("ix_optical_device_device_type", "optical_device", ["device_type"])
    op.create_index("ix_optical_device_status", "optical_device", ["status"])

    op.create_table(
        "optical_port",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("port_kind", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="available"),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "port_kind IN ('pon', 'adapter', 'splitter_input', 'splitter_output', "
            "'cto_distribution')",
            name="ck_optical_port_kind",
        ),
        sa.CheckConstraint("position > 0", name="ck_optical_port_position"),
        sa.CheckConstraint(
            "status IN ('available', 'reserved', 'occupied', 'damaged', 'deactivated')",
            name="ck_optical_port_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["device_id"], ["optical_device.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "port_kind", "position", name="uq_optical_port_position"),
    )
    op.create_index("ix_optical_port_device_id", "optical_port", ["device_id"])
    op.create_index("ix_optical_port_status", "optical_port", ["status"])


def downgrade() -> None:
    op.drop_index("ix_optical_port_status", table_name="optical_port")
    op.drop_index("ix_optical_port_device_id", table_name="optical_port")
    op.drop_table("optical_port")
    op.drop_index("ix_optical_device_status", table_name="optical_device")
    op.drop_index("ix_optical_device_device_type", table_name="optical_device")
    op.drop_table("optical_device")
