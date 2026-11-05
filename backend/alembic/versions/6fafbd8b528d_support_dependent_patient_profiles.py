"""support dependent patient profiles

Revision ID: 6fafbd8b528d
Revises: 4340458f304b
Create Date: 2026-11-05 09:34:12.610081
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6fafbd8b528d"
down_revision: str | None = "4340458f304b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    unique = next(
        (
            item
            for item in sa.inspect(bind).get_unique_constraints("patient_profiles")
            if item["column_names"] == ["user_id"]
        ),
        None,
    )
    if unique:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(
                "patient_profiles",
                naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
            ) as batch:
                batch.drop_constraint(
                    unique["name"] or "uq_patient_profiles_user_id", type_="unique"
                )
                batch.add_column(
                    sa.Column("relationship_label", sa.String(length=60), nullable=True)
                )
        else:
            op.drop_constraint(unique["name"], "patient_profiles", type_="unique")
            op.add_column(
                "patient_profiles",
                sa.Column("relationship_label", sa.String(length=60), nullable=True),
            )
    else:
        columns = {column["name"] for column in sa.inspect(bind).get_columns("patient_profiles")}
        if "relationship_label" not in columns:
            op.add_column(
                "patient_profiles",
                sa.Column("relationship_label", sa.String(length=60), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    profile_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM patient_profiles GROUP BY user_id HAVING COUNT(*) > 1")
    ).first()
    if profile_count:
        raise RuntimeError("Cannot downgrade while dependent profiles exist")
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("patient_profiles") as batch:
            batch.create_unique_constraint("uq_patient_profiles_user_id", ["user_id"])
            batch.drop_column("relationship_label")
    else:
        op.create_unique_constraint("uq_patient_profiles_user_id", "patient_profiles", ["user_id"])
        op.drop_column("patient_profiles", "relationship_label")
