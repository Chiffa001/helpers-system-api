"""Add groups, group members, and group-scoped invites."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f2a1f6d7b9c3"
down_revision: str | None = "9f3a1b0e4c2d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


group_status_check = sa.CheckConstraint(
    "status IN ('active', 'archived')",
    name="ck_groups_status",
)
group_member_role_check = sa.CheckConstraint(
    "role IN ('assistant', 'client')",
    name="ck_group_members_role",
)


def upgrade() -> None:
    op.create_table(
        "groups",
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
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
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
        group_status_check,
    )
    op.create_index("idx_groups_workspace", "groups", ["workspace_id"])
    op.create_index("idx_groups_status", "groups", ["status"])

    op.create_table(
        "group_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
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
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_members_group_user"),
        group_member_role_check,
    )
    op.create_index("idx_group_members_group", "group_members", ["group_id"])
    op.create_index("idx_group_members_user", "group_members", ["user_id"])

    op.add_column("workspace_invites", sa.Column("group_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_workspace_invites_group_id_groups",
        "workspace_invites",
        "groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_workspace_invites_group_id", "workspace_invites", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_workspace_invites_group_id", table_name="workspace_invites")
    op.drop_constraint(
        "fk_workspace_invites_group_id_groups",
        "workspace_invites",
        type_="foreignkey",
    )
    op.drop_column("workspace_invites", "group_id")

    op.drop_index("idx_group_members_user", table_name="group_members")
    op.drop_index("idx_group_members_group", table_name="group_members")
    op.drop_table("group_members")

    op.drop_index("idx_groups_status", table_name="groups")
    op.drop_index("idx_groups_workspace", table_name="groups")
    op.drop_table("groups")
