"""Add service networks, feature grouping and geocoding cache.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_network",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=80), nullable=False),
        sa.Column("country", sa.String(length=80), nullable=False, server_default="Brasil"),
        sa.Column("viewport", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_service_network_city", "service_network", ["city"])

    op.add_column(
        "map_feature",
        sa.Column("network_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_map_feature_network_id",
        "map_feature",
        "service_network",
        ["network_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_map_feature_network_id", "map_feature", ["network_id"])

    op.add_column(
        "map_import",
        sa.Column("network_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_map_import_network_id",
        "map_import",
        "service_network",
        ["network_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_map_import_network_id", "map_import", ["network_id"])

    op.create_table(
        "geocode_cache",
        sa.Column("query_key", sa.String(length=64), nullable=False),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("query_key"),
    )
    op.create_index("ix_geocode_cache_expires_at", "geocode_cache", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_geocode_cache_expires_at", table_name="geocode_cache")
    op.drop_table("geocode_cache")
    op.drop_index("ix_map_import_network_id", table_name="map_import")
    op.drop_constraint("fk_map_import_network_id", "map_import", type_="foreignkey")
    op.drop_column("map_import", "network_id")
    op.drop_index("ix_map_feature_network_id", table_name="map_feature")
    op.drop_constraint("fk_map_feature_network_id", "map_feature", type_="foreignkey")
    op.drop_column("map_feature", "network_id")
    op.drop_index("ix_service_network_city", table_name="service_network")
    op.drop_table("service_network")
