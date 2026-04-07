"""add workspace invites"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c2b7a66d9c44"
down_revision: str | None = "db5c339b4f78"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


workspace_invite_role_check = sa.CheckConstraint(
    "role IN ('workspace_admin', 'assistant', 'client')",
    name="ck_workspace_invites_role",
)


def upgrade() -> None:
    op.create_table(
        "workspace_invites",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "token",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "used_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "used_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("token", name="uq_workspace_invites_token"),
        workspace_invite_role_check,
    )
    op.create_index("idx_workspace_invites_token", "workspace_invites", ["token"])
    op.create_index("idx_workspace_invites_workspace", "workspace_invites", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("idx_workspace_invites_workspace", table_name="workspace_invites")
    op.drop_index("idx_workspace_invites_token", table_name="workspace_invites")
    op.drop_table("workspace_invites")
