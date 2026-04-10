from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.billing_payment import BillingPayment
from app.models.enums import BillingPaymentStatus, SubscriptionStatus, WorkspacePlan
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.workspace_subscription import WorkspaceSubscription
from app.modules.billing.schemas import (
    PLAN_LIMITS,
    PLAN_PRICES,
    AdminPlanOverrideRequest,
    BillingInfoResponse,
    BillingLimitsUsage,
    BillingPaymentOut,
    PlanLimits,
    PlanLimitUsage,
    PlanOut,
    SubscriptionOut,
)


class BillingService:
    def __init__(self, session: Annotated[AsyncSession, Depends(get_db_session)]) -> None:
        self.session = session

    async def get_billing_info(self, workspace: Workspace) -> BillingInfoResponse:
        subscription = await self._active_subscription(workspace.id)

        member_count = await self._count_members(workspace.id)
        limits = PLAN_LIMITS[workspace.plan]

        limits_usage = BillingLimitsUsage(
            members=PlanLimitUsage(
                current=member_count,
                max=limits["members"],
            ),
            projects=PlanLimitUsage(
                current=0,
                max=limits["projects"],
            ),
        )

        recent_payments = await self._recent_payments(workspace.id, limit=3)

        return BillingInfoResponse(
            plan=workspace.plan,
            fee_rate=workspace.fee_rate,
            subscription=SubscriptionOut.model_validate(subscription) if subscription else None,
            limits_usage=limits_usage,
            recent_payments=[BillingPaymentOut.model_validate(p) for p in recent_payments],
        )

    async def list_plans(self, workspace: Workspace) -> list[PlanOut]:
        result = []
        for plan in WorkspacePlan:
            prices = PLAN_PRICES[plan]
            raw_limits = PLAN_LIMITS[plan]
            result.append(
                PlanOut(
                    plan=plan,
                    price_monthly=prices["monthly"],
                    price_annual=prices["annual"],
                    limits=PlanLimits(
                        members=raw_limits["members"],
                        projects=raw_limits["projects"],
                        crypto=raw_limits["crypto"],
                    ),
                    is_current=workspace.plan == plan,
                )
            )
        return result

    async def admin_override_plan(
        self,
        workspace: Workspace,
        payload: AdminPlanOverrideRequest,
    ) -> BillingInfoResponse:
        if payload.plan == WorkspacePlan.FREE:
            await self._cancel_active_subscriptions(workspace.id)
            workspace.plan = WorkspacePlan.FREE
            await self.session.commit()
            await self.session.refresh(workspace)
            return await self.get_billing_info(workspace)

        prices = PLAN_PRICES[payload.plan]
        amount = prices[payload.billing_period.value]
        now = datetime.now(UTC)

        if payload.expires_at is not None:
            expires_at = payload.expires_at
        elif payload.billing_period.value == "annual":
            expires_at = now + timedelta(days=365)
        else:
            expires_at = now + timedelta(days=30)

        if expires_at.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="expires_at must include timezone info",
            )

        await self._cancel_active_subscriptions(workspace.id)

        subscription = WorkspaceSubscription(
            workspace_id=workspace.id,
            plan=payload.plan,
            billing_period=payload.billing_period,
            status=SubscriptionStatus.ACTIVE,
            started_at=now,
            expires_at=expires_at,
            auto_renew=False,
        )
        self.session.add(subscription)
        await self.session.flush()

        payment = BillingPayment(
            workspace_id=workspace.id,
            subscription_id=subscription.id,
            amount=amount,
            currency="RUB",
            status=BillingPaymentStatus.PAID,
            paid_at=now,
            description=(
                f"{payload.plan.value.capitalize()} — {payload.billing_period.value} (manual)"
            ),
        )
        self.session.add(payment)

        workspace.plan = payload.plan
        await self.session.commit()
        await self.session.refresh(workspace)

        return await self.get_billing_info(workspace)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _active_subscription(self, workspace_id: UUID) -> WorkspaceSubscription | None:
        result = await self.session.scalar(
            select(WorkspaceSubscription)
            .where(
                WorkspaceSubscription.workspace_id == workspace_id,
                WorkspaceSubscription.status == SubscriptionStatus.ACTIVE,
            )
            .order_by(WorkspaceSubscription.created_at.desc())
            .limit(1)
        )
        return result

    async def _cancel_active_subscriptions(self, workspace_id: UUID) -> None:
        result = await self.session.scalars(
            select(WorkspaceSubscription).where(
                WorkspaceSubscription.workspace_id == workspace_id,
                WorkspaceSubscription.status == SubscriptionStatus.ACTIVE,
            )
        )
        now = datetime.now(UTC)
        for sub in result.all():
            sub.status = SubscriptionStatus.CANCELLED
            sub.cancelled_at = now
            sub.auto_renew = False

    async def _count_members(self, workspace_id: UUID) -> int:
        result = await self.session.scalars(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.is_active.is_(True),
            )
        )
        return len(result.all())

    async def _recent_payments(self, workspace_id: UUID, limit: int = 3) -> list[BillingPayment]:
        result = await self.session.scalars(
            select(BillingPayment)
            .where(BillingPayment.workspace_id == workspace_id)
            .order_by(BillingPayment.created_at.desc())
            .limit(limit)
        )
        return list(result.all())
