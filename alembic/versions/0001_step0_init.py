"""Step 0 initial schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_step0_init"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


workspace_status_check = sa.CheckConstraint(
    "status IN ('active', 'suspended', 'archived')",
    name="ck_workspaces_status",
)
workspace_plan_check = sa.CheckConstraint(
    "plan IN ('free', 'basic', 'pro', 'business')",
    name="ck_workspaces_plan",
)
workspace_member_role_check = sa.CheckConstraint(
    "role IN ('workspace_admin', 'assistant', 'client')",
    name="ck_workspace_members_role",
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("is_super_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "workspaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("plan", sa.Text(), nullable=False, server_default=sa.text("'free'")),
        sa.Column("fee_rate", sa.Numeric(5, 4), nullable=False, server_default=sa.text("0.03")),
        sa.Column(
            "created_by_user_id",
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
        sa.UniqueConstraint("slug"),
        workspace_status_check,
        workspace_plan_check,
    )
    op.create_index("idx_workspaces_slug", "workspaces", ["slug"])
    op.create_index("idx_workspaces_status", "workspaces", ["status"])

    op.create_table(
        "workspace_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "joined_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("workspace_id", "user_id"),
        workspace_member_role_check,
    )
    op.create_index("idx_wm_workspace", "workspace_members", ["workspace_id"])
    op.create_index("idx_wm_user", "workspace_members", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_wm_user", table_name="workspace_members")
    op.drop_index("idx_wm_workspace", table_name="workspace_members")
    op.drop_table("workspace_members")
    op.drop_index("idx_workspaces_status", table_name="workspaces")
    op.drop_index("idx_workspaces_slug", table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_table("users")
