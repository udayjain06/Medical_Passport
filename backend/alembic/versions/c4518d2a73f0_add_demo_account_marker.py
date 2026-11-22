"""mark the reserved synthetic demo account"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4518d2a73f0"
down_revision: str | None = "ae7c2c3bd516"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "is_demo")
