"""Add group favorites."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e8c9d2a4b771"
down_revision: str | None = "c4d8e1f0ab12"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "group_favorites",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "group_id", name="uq_group_favorites_user_group"),
    )
    op.create_index("idx_group_favorites_user", "group_favorites", ["user_id"])
    op.create_index("idx_group_favorites_group", "group_favorites", ["group_id"])


def downgrade() -> None:
    op.drop_index("idx_group_favorites_group", table_name="group_favorites")
    op.drop_index("idx_group_favorites_user", table_name="group_favorites")
    op.drop_table("group_favorites")
