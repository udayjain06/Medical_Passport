"""record per-extraction AI consent and provider use

Revision ID: ae7c2c3bd516
Revises: d3a42e0976bf
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ae7c2c3bd516"
down_revision: str | None = "d3a42e0976bf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_extractions",
        sa.Column("ai_consent", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("document_extractions", sa.Column("ai_consent_at", sa.DateTime(timezone=True)))
    op.add_column("document_extractions", sa.Column("ai_provider", sa.String(length=120)))
    op.add_column("document_extractions", sa.Column("ai_processed_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("document_extractions", "ai_processed_at")
    op.drop_column("document_extractions", "ai_provider")
    op.drop_column("document_extractions", "ai_consent_at")
    op.drop_column("document_extractions", "ai_consent")
