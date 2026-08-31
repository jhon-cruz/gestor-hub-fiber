"""Add idempotent geographic import tracking.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "map_import",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("source_namespace", sa.String(length=120), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_format", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("feature_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_map_import_created_at", "map_import", ["created_at"])
    op.create_index("ix_map_import_source_namespace", "map_import", ["source_namespace"])
    op.create_index(
        "uq_map_import_source_hash",
        "map_import",
        ["source_namespace", "file_sha256"],
        unique=True,
    )

    op.add_column(
        "map_feature",
        sa.Column("import_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "map_feature",
        sa.Column("source_namespace", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "map_feature",
        sa.Column("source_ref", sa.String(length=160), nullable=True),
    )
    op.create_foreign_key(
        "fk_map_feature_import_id",
        "map_feature",
        "map_import",
        ["import_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_map_feature_import_id", "map_feature", ["import_id"])
    op.create_index(
        "uq_map_feature_source",
        "map_feature",
        ["source_namespace", "source_ref"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_map_feature_source", table_name="map_feature")
    op.drop_index("ix_map_feature_import_id", table_name="map_feature")
    op.drop_constraint("fk_map_feature_import_id", "map_feature", type_="foreignkey")
    op.drop_column("map_feature", "source_ref")
    op.drop_column("map_feature", "source_namespace")
    op.drop_column("map_feature", "import_id")
    op.drop_index("uq_map_import_source_hash", table_name="map_import")
    op.drop_index("ix_map_import_source_namespace", table_name="map_import")
    op.drop_index("ix_map_import_created_at", table_name="map_import")
    op.drop_table("map_import")
