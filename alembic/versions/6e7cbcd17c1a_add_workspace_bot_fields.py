"""add workspace bot fields"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "6e7cbcd17c1a"
down_revision: str | None = "c2b7a66d9c44"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("bot_token", sa.Text(), nullable=True))
    op.add_column("workspaces", sa.Column("bot_username", sa.Text(), nullable=True))
    op.add_column("workspaces", sa.Column("mini_app_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("workspaces", "mini_app_url")
    op.drop_column("workspaces", "bot_username")
    op.drop_column("workspaces", "bot_token")
