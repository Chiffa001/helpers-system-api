"""add billing tables"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "6e7cbcd17c1a"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

subscription_plan_check = sa.CheckConstraint(
    "plan IN ('free', 'basic', 'pro', 'business')",
    name="ck_ws_subscriptions_plan",
)
subscription_period_check = sa.CheckConstraint(
    "billing_period IN ('monthly', 'annual')",
    name="ck_ws_subscriptions_period",
)
subscription_status_check = sa.CheckConstraint(
    "status IN ('active', 'cancelled', 'expired', 'past_due')",
    name="ck_ws_subscriptions_status",
)
subscription_provider_check = sa.CheckConstraint(
    "provider IN ('manual')",
    name="ck_ws_subscriptions_provider",
)
payment_status_check = sa.CheckConstraint(
    "status IN ('pending', 'paid', 'failed', 'refunded')",
    name="ck_billing_payments_status",
)


def upgrade() -> None:
    op.create_table(
        "workspace_subscriptions",
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
        sa.Column("plan", sa.Text(), nullable=False),
        sa.Column("billing_period", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("provider", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("provider_subscription_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        subscription_plan_check,
        subscription_period_check,
        subscription_status_check,
        subscription_provider_check,
    )
    op.create_index("idx_ws_subscriptions_workspace", "workspace_subscriptions", ["workspace_id"])

    op.create_table(
        "billing_payments",
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
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspace_subscriptions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'RUB'")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'paid'")),
        sa.Column("paid_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("payment_method_last4", sa.String(4), nullable=True),
        sa.Column("provider_payment_id", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        payment_status_check,
    )
    op.create_index("idx_billing_payments_workspace", "billing_payments", ["workspace_id"])
    op.create_index("idx_billing_payments_subscription", "billing_payments", ["subscription_id"])


def downgrade() -> None:
    op.drop_index("idx_billing_payments_subscription", table_name="billing_payments")
    op.drop_index("idx_billing_payments_workspace", table_name="billing_payments")
    op.drop_table("billing_payments")
    op.drop_index("idx_ws_subscriptions_workspace", table_name="workspace_subscriptions")
    op.drop_table("workspace_subscriptions")
