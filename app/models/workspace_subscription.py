from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import BillingPeriod, BillingProvider, SubscriptionStatus, WorkspacePlan


class WorkspaceSubscription(Base):
    __tablename__ = "workspace_subscriptions"

    plan_enum = Enum(
        WorkspacePlan,
        native_enum=False,
        values_callable=lambda enum_cls: [item.value for item in enum_cls],
    )
    period_enum = Enum(
        BillingPeriod,
        native_enum=False,
        values_callable=lambda enum_cls: [item.value for item in enum_cls],
    )
    status_enum = Enum(
        SubscriptionStatus,
        native_enum=False,
        values_callable=lambda enum_cls: [item.value for item in enum_cls],
    )
    provider_enum = Enum(
        BillingProvider,
        native_enum=False,
        values_callable=lambda enum_cls: [item.value for item in enum_cls],
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan: Mapped[WorkspacePlan] = mapped_column(plan_enum, nullable=False)
    billing_period: Mapped[BillingPeriod] = mapped_column(period_enum, nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        status_enum,
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    provider: Mapped[BillingProvider] = mapped_column(
        provider_enum,
        nullable=False,
        default=BillingProvider.MANUAL,
    )
    provider_subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    workspace = relationship("Workspace", back_populates="subscriptions")
    payments = relationship("BillingPayment", back_populates="subscription")
