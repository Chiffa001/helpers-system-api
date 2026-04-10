from datetime import datetime
from decimal import Decimal
from typing import TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    BillingPaymentStatus,
    BillingPeriod,
    BillingProvider,
    SubscriptionStatus,
    WorkspacePlan,
)

# ---------------------------------------------------------------------------
# Plan catalogue
# ---------------------------------------------------------------------------


class PlanPriceMap(TypedDict):
    monthly: int
    annual: int


class PlanLimitsMap(TypedDict):
    members: int | None
    projects: int | None
    crypto: bool


PLAN_PRICES: dict[WorkspacePlan, PlanPriceMap] = {
    WorkspacePlan.FREE: {"monthly": 0, "annual": 0},
    WorkspacePlan.BASIC: {"monthly": 990, "annual": 9900},
    WorkspacePlan.PRO: {"monthly": 2490, "annual": 24900},
    WorkspacePlan.BUSINESS: {"monthly": 7490, "annual": 74900},
}

PLAN_LIMITS: dict[WorkspacePlan, PlanLimitsMap] = {
    WorkspacePlan.FREE: {"members": 5, "projects": 1, "crypto": False},
    WorkspacePlan.BASIC: {"members": 20, "projects": 5, "crypto": True},
    WorkspacePlan.PRO: {"members": 50, "projects": None, "crypto": True},
    WorkspacePlan.BUSINESS: {"members": None, "projects": None, "crypto": True},
}


# ---------------------------------------------------------------------------
# Shared sub-schemas
# ---------------------------------------------------------------------------


class PlanLimits(BaseModel):
    members: int | None
    projects: int | None
    crypto: bool


class PlanLimitUsage(BaseModel):
    current: int
    max: int | None


class BillingLimitsUsage(BaseModel):
    members: PlanLimitUsage
    projects: PlanLimitUsage


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------


class SubscriptionOut(BaseModel):
    id: UUID
    plan: WorkspacePlan
    billing_period: BillingPeriod
    status: SubscriptionStatus
    started_at: datetime
    expires_at: datetime
    cancelled_at: datetime | None
    auto_renew: bool
    provider: BillingProvider

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Billing payment
# ---------------------------------------------------------------------------


class BillingPaymentOut(BaseModel):
    id: UUID
    amount: Decimal
    currency: str
    status: BillingPaymentStatus
    paid_at: datetime | None
    payment_method_last4: str | None
    description: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# GET /workspaces/{id}/billing
# ---------------------------------------------------------------------------


class BillingInfoResponse(BaseModel):
    plan: WorkspacePlan
    fee_rate: Decimal
    subscription: SubscriptionOut | None
    limits_usage: BillingLimitsUsage
    recent_payments: list[BillingPaymentOut]


# ---------------------------------------------------------------------------
# GET /workspaces/{id}/billing/plans
# ---------------------------------------------------------------------------


class PlanOut(BaseModel):
    plan: WorkspacePlan
    price_monthly: int
    price_annual: int
    limits: PlanLimits
    is_current: bool


# ---------------------------------------------------------------------------
# PATCH /workspaces/{id}/billing/admin
# ---------------------------------------------------------------------------


class AdminPlanOverrideRequest(BaseModel):
    plan: WorkspacePlan
    expires_at: datetime | None = None
    billing_period: BillingPeriod = BillingPeriod.MONTHLY
