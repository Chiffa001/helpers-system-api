"""Align group event and invoice contracts with documented API."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d91f0a6b3c2e"
down_revision: str | None = "b7f9c3a21d4e"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

group_event_participant_status_check = sa.CheckConstraint(
    "status IN ('invited', 'confirmed_free', 'pending_payment', 'paid', 'cancelled')",
    name="ck_group_event_participants_status",
)


def upgrade() -> None:
    op.add_column("group_events", sa.Column("location", sa.Text(), nullable=True))
    op.add_column("group_events", sa.Column("currency", sa.String(length=3), nullable=True))
    op.add_column("group_events", sa.Column("due_date", sa.TIMESTAMP(timezone=True), nullable=True))

    op.alter_column("invoices", "payment_tx_hash", new_column_name="tx_hash")

    op.create_table(
        "group_event_participants",
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
            sa.ForeignKey("group_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'invited'")),
        sa.Column(
            "is_paid_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "group_event_id",
            "user_id",
            name="uq_group_event_participants_event_user",
        ),
        group_event_participant_status_check,
    )
    op.create_index(
        "idx_group_event_participants_group_event",
        "group_event_participants",
        ["group_event_id"],
    )
    op.create_index(
        "idx_group_event_participants_user",
        "group_event_participants",
        ["user_id"],
    )
    op.create_index(
        "idx_group_event_participants_status",
        "group_event_participants",
        ["status"],
    )
    op.create_index(
        "idx_group_event_participants_invoice",
        "group_event_participants",
        ["invoice_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_group_event_participants_invoice",
        table_name="group_event_participants",
    )
    op.drop_index(
        "idx_group_event_participants_status",
        table_name="group_event_participants",
    )
    op.drop_index(
        "idx_group_event_participants_user",
        table_name="group_event_participants",
    )
    op.drop_index(
        "idx_group_event_participants_group_event",
        table_name="group_event_participants",
    )
    op.drop_table("group_event_participants")

    op.alter_column("invoices", "tx_hash", new_column_name="payment_tx_hash")

    op.drop_column("group_events", "due_date")
    op.drop_column("group_events", "currency")
    op.drop_column("group_events", "location")
