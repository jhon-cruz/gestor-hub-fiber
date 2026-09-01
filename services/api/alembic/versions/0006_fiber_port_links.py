"""Connect fiber extremities to optical equipment ports.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fiber_port_link",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fiber_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fiber_end", sa.String(length=1), nullable=False),
        sa.Column("port_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("port_side", sa.String(length=1), nullable=False, server_default="a"),
        sa.Column("insertion_loss_db", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("fiber_end IN ('a', 'b')", name="ck_fiber_port_link_end"),
        sa.CheckConstraint("port_side IN ('a', 'b')", name="ck_fiber_port_link_side"),
        sa.CheckConstraint("insertion_loss_db >= 0", name="ck_fiber_port_link_loss"),
        sa.ForeignKeyConstraint(["fiber_id"], ["optical_fiber.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["port_id"], ["optical_port.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fiber_id", "fiber_end", name="uq_fiber_port_link_fiber_end"),
        sa.UniqueConstraint("port_id", "port_side", name="uq_fiber_port_link_port_side"),
    )
    op.create_index("ix_fiber_port_link_fiber", "fiber_port_link", ["fiber_id"])
    op.create_index("ix_fiber_port_link_port", "fiber_port_link", ["port_id"])


def downgrade() -> None:
    op.drop_index("ix_fiber_port_link_port", table_name="fiber_port_link")
    op.drop_index("ix_fiber_port_link_fiber", table_name="fiber_port_link")
    op.drop_table("fiber_port_link")
