"""emergency access log and share labels

Revision ID: b1c4e7a90d25
Revises: 9a7c2d41b6e0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c4e7a90d25"
down_revision: str | None = "9a7c2d41b6e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("emergency_shares", sa.Column("label", sa.String(length=80), nullable=True))
    op.create_table(
        "emergency_access_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("share_id", sa.Uuid(), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_prefix", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=160), nullable=True),
        sa.ForeignKeyConstraint(["share_id"], ["emergency_shares.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_emergency_access_logs_share_id"), "emergency_access_logs", ["share_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_emergency_access_logs_share_id"), table_name="emergency_access_logs")
    op.drop_table("emergency_access_logs")
    op.drop_column("emergency_shares", "label")
