"""Add workspace events tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b7f9c3a21d4e"
down_revision: str | None = "e8c9d2a4b771"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


workspace_event_audience_check = sa.CheckConstraint(
    "audience IN ('all', 'assistants', 'admins')",
    name="ck_workspace_events_audience",
)
workspace_event_status_check = sa.CheckConstraint(
    "status IN ('upcoming', 'completed', 'cancelled')",
    name="ck_workspace_events_status",
)
workspace_event_response_check = sa.CheckConstraint(
    "response IN ('pending', 'accepted', 'declined')",
    name="ck_workspace_event_participants_response",
)


def upgrade() -> None:
    op.create_table(
        "workspace_events",
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
        sa.Column("date", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("audience", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'upcoming'")),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        workspace_event_audience_check,
        workspace_event_status_check,
    )
    op.create_index(
        "idx_workspace_events_workspace_status",
        "workspace_events",
        ["workspace_id", "status"],
    )
    op.create_index("idx_workspace_events_date", "workspace_events", ["date"])
    op.create_index(
        "idx_workspace_events_workspace_audience",
        "workspace_events",
        ["workspace_id", "audience"],
    )
    op.create_index(
        "idx_workspace_events_created_by_user",
        "workspace_events",
        ["created_by_user_id"],
    )

    op.create_table(
        "workspace_event_participants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspace_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("response", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("responded_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "workspace_event_id",
            "user_id",
            name="uq_workspace_event_participants_event_user",
        ),
        workspace_event_response_check,
    )
    op.create_index(
        "idx_workspace_event_participants_event_response",
        "workspace_event_participants",
        ["workspace_event_id", "response"],
    )
    op.create_index(
        "idx_workspace_event_participants_user_event",
        "workspace_event_participants",
        ["user_id", "workspace_event_id"],
    )

    op.create_table(
        "workspace_event_groups",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspace_events.id", ondelete="CASCADE"),
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
        sa.UniqueConstraint(
            "workspace_event_id",
            "group_id",
            name="uq_workspace_event_groups_event_group",
        ),
    )
    op.create_index(
        "idx_workspace_event_groups_event",
        "workspace_event_groups",
        ["workspace_event_id"],
    )
    op.create_index("idx_workspace_event_groups_group", "workspace_event_groups", ["group_id"])


def downgrade() -> None:
    op.drop_index("idx_workspace_event_groups_group", table_name="workspace_event_groups")
    op.drop_index("idx_workspace_event_groups_event", table_name="workspace_event_groups")
    op.drop_table("workspace_event_groups")

    op.drop_index(
        "idx_workspace_event_participants_user_event",
        table_name="workspace_event_participants",
    )
    op.drop_index(
        "idx_workspace_event_participants_event_response",
        table_name="workspace_event_participants",
    )
    op.drop_table("workspace_event_participants")

    op.drop_index("idx_workspace_events_created_by_user", table_name="workspace_events")
    op.drop_index("idx_workspace_events_workspace_audience", table_name="workspace_events")
    op.drop_index("idx_workspace_events_date", table_name="workspace_events")
    op.drop_index("idx_workspace_events_workspace_status", table_name="workspace_events")
    op.drop_table("workspace_events")
