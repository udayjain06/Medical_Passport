"""record account consents and emergency-share ownership

Revision ID: d3a42e0976bf
Revises: 4e80c5365ab2
Create Date: 2026-11-17
"""

from alembic import op
import sqlalchemy as sa

revision = "d3a42e0976bf"
down_revision = "4e80c5365ab2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consent_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consent_records_user_id", "consent_records", ["user_id"])
    op.create_index(
        "ix_consent_records_user_granted",
        "consent_records",
        ["user_id", "granted_at"],
    )

    with op.batch_alter_table("emergency_shares") as batch:
        batch.add_column(sa.Column("created_by_user_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_emergency_shares_created_by_user_id_users",
            "users",
            ["created_by_user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_index(
            "ix_emergency_shares_created_by_user_id", ["created_by_user_id"], unique=False
        )

    op.execute(
        "UPDATE emergency_shares "
        "SET created_by_user_id = ("
        "SELECT user_id FROM patient_profiles "
        "WHERE patient_profiles.id = emergency_shares.profile_id)"
    )
    with op.batch_alter_table("emergency_shares") as batch:
        batch.alter_column(
            "created_by_user_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("emergency_shares") as batch:
        batch.drop_index("ix_emergency_shares_created_by_user_id")
        batch.drop_constraint("fk_emergency_shares_created_by_user_id_users", type_="foreignkey")
        batch.drop_column("created_by_user_id")
    op.drop_index("ix_consent_records_user_granted", table_name="consent_records")
    op.drop_index("ix_consent_records_user_id", table_name="consent_records")
    op.drop_table("consent_records")
