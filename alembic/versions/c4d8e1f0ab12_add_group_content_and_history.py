"""Add group content, invoices, and history tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c4d8e1f0ab12"
down_revision: str | None = "f2a1f6d7b9c3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


group_stage_status_check = sa.CheckConstraint(
    "status IN ('todo', 'in_progress', 'done')",
    name="ck_group_stages_status",
)
group_event_status_check = sa.CheckConstraint(
    "status IN ('upcoming', 'completed', 'cancelled')",
    name="ck_group_events_status",
)
invoice_status_check = sa.CheckConstraint(
    "status IN ('issued', 'pending_payment', 'paid', 'cancelled', 'expired')",
    name="ck_invoices_status",
)
group_history_event_type_check = sa.CheckConstraint(
    "event_type IN ("
    "'stage_status_changed', 'invoice_issued', 'invoice_paid', 'invoice_cancelled', "
    "'invoice_expired', 'event_created', 'event_cancelled', 'document_added', "
    "'member_added', 'member_removed'"
    ")",
    name="ck_group_history_entries_event_type",
)


def upgrade() -> None:
    op.create_table(
        "group_documents",
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
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
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
    )
    op.create_index("idx_group_documents_group", "group_documents", ["group_id"])

    op.create_table(
        "group_stages",
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
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'todo'")),
        sa.Column(
            "assigned_to_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("due_date", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        group_stage_status_check,
    )
    op.create_index("idx_group_stages_group", "group_stages", ["group_id"])
    op.create_index("idx_group_stages_status", "group_stages", ["status"])

    op.create_table(
        "group_events",
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
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("date", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'upcoming'")),
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
        group_event_status_check,
    )
    op.create_index("idx_group_events_group", "group_events", ["group_id"])
    op.create_index("idx_group_events_status", "group_events", ["status"])
    op.create_index("idx_group_events_date", "group_events", ["date"])

    op.create_table(
        "invoices",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "group_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("group_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "client_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'issued'")),
        sa.Column("due_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("payment_tx_hash", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        invoice_status_check,
    )
    op.create_index("idx_invoices_group", "invoices", ["group_id"])
    op.create_index("idx_invoices_client_user", "invoices", ["client_user_id"])
    op.create_index("idx_invoices_group_event", "invoices", ["group_event_id"])
    op.create_index("idx_invoices_status", "invoices", ["status"])

    op.create_table(
        "group_history_entries",
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
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        group_history_event_type_check,
    )
    op.create_index("idx_group_history_entries_group", "group_history_entries", ["group_id"])
    op.create_index(
        "idx_group_history_entries_actor_user",
        "group_history_entries",
        ["actor_user_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_group_history_entries_actor_user", table_name="group_history_entries")
    op.drop_index("idx_group_history_entries_group", table_name="group_history_entries")
    op.drop_table("group_history_entries")

    op.drop_index("idx_invoices_status", table_name="invoices")
    op.drop_index("idx_invoices_group_event", table_name="invoices")
    op.drop_index("idx_invoices_client_user", table_name="invoices")
    op.drop_index("idx_invoices_group", table_name="invoices")
    op.drop_table("invoices")

    op.drop_index("idx_group_events_date", table_name="group_events")
    op.drop_index("idx_group_events_status", table_name="group_events")
    op.drop_index("idx_group_events_group", table_name="group_events")
    op.drop_table("group_events")

    op.drop_index("idx_group_stages_status", table_name="group_stages")
    op.drop_index("idx_group_stages_group", table_name="group_stages")
    op.drop_table("group_stages")

    op.drop_index("idx_group_documents_group", table_name="group_documents")
    op.drop_table("group_documents")
