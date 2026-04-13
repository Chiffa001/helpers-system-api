from datetime import UTC, datetime, timedelta
from typing import TypedDict
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.enums import BillingPeriod, SubscriptionStatus, WorkspacePlan, WorkspaceRole
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.workspace_subscription import WorkspaceSubscription


class SeededBillingData(TypedDict):
    workspace: Workspace
    admin: User
    super_admin: User
    outsider: User


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        user_id=str(user.id),
        is_super_admin=user.is_super_admin,
        settings=get_settings(),
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_billing_data(db_session: AsyncSession) -> SeededBillingData:
    suffix = uuid4().hex[:8]
    telegram_seed = uuid4().int % 100_000_000

    workspace = Workspace(
        title=f"Billing Workspace {suffix}",
        slug=f"billing-ws-{suffix}",
    )
    admin = User(
        telegram_id=7_900_000_000 + telegram_seed,
        full_name="Billing Admin",
        username="billing_admin",
    )
    super_admin = User(
        telegram_id=7_901_000_000 + telegram_seed,
        full_name="Super Admin",
        username="super_admin_billing",
        is_super_admin=True,
    )
    outsider = User(
        telegram_id=7_902_000_000 + telegram_seed,
        full_name="Outsider",
        username="outsider_billing",
    )

    db_session.add_all([workspace, admin, super_admin, outsider])
    await db_session.flush()

    db_session.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=admin.id,
            role=WorkspaceRole.WORKSPACE_ADMIN,
            is_active=True,
            joined_at=datetime(2026, 1, 10, 10, 0, tzinfo=UTC),
        )
    )
    await db_session.commit()

    return {
        "workspace": workspace,
        "admin": admin,
        "super_admin": super_admin,
        "outsider": outsider,
    }


# ---------------------------------------------------------------------------
# GET /workspaces/{id}/billing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_billing_info_returns_free_plan(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_billing_data(db_session)
    workspace = data["workspace"]

    response = await client.get(
        f"/workspaces/{workspace.id}/billing",
        headers=_auth_headers(data["admin"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"] == "free"
    assert body["subscription"] is None
    assert body["limits_usage"]["members"]["max"] == 5
    assert body["limits_usage"]["projects"]["max"] == 1
    assert body["recent_payments"] == []
    await db_session.close()


@pytest.mark.asyncio
async def test_get_billing_info_shows_active_subscription(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_billing_data(db_session)
    workspace = data["workspace"]
    workspace.plan = WorkspacePlan.PRO

    now = datetime.now(UTC)
    subscription = WorkspaceSubscription(
        workspace_id=workspace.id,
        plan=WorkspacePlan.PRO,
        billing_period=BillingPeriod.MONTHLY,
        status=SubscriptionStatus.ACTIVE,
        started_at=now,
        expires_at=now + timedelta(days=30),
        auto_renew=True,
    )
    db_session.add(subscription)
    await db_session.commit()

    response = await client.get(
        f"/workspaces/{workspace.id}/billing",
        headers=_auth_headers(data["admin"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"] == "pro"
    assert body["subscription"] is not None
    assert body["subscription"]["status"] == "active"
    assert body["subscription"]["billing_period"] == "monthly"
    assert body["limits_usage"]["members"]["max"] == 50
    await db_session.close()


@pytest.mark.asyncio
async def test_get_billing_info_requires_admin_role(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_billing_data(db_session)

    response = await client.get(
        f"/workspaces/{data['workspace'].id}/billing",
        headers=_auth_headers(data["outsider"]),
    )

    assert response.status_code == 403
    await db_session.close()


# ---------------------------------------------------------------------------
# GET /workspaces/{id}/billing/plans
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_plans_returns_all_four_plans(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_billing_data(db_session)

    response = await client.get(
        f"/workspaces/{data['workspace'].id}/billing/plans",
        headers=_auth_headers(data["admin"]),
    )

    assert response.status_code == 200
    plans = response.json()
    plan_names = [p["plan"] for p in plans]
    assert set(plan_names) == {"free", "basic", "pro", "business"}
    await db_session.close()


@pytest.mark.asyncio
async def test_list_plans_marks_current_plan(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_billing_data(db_session)

    response = await client.get(
        f"/workspaces/{data['workspace'].id}/billing/plans",
        headers=_auth_headers(data["admin"]),
    )

    assert response.status_code == 200
    plans = response.json()
    current_plans = [p for p in plans if p["is_current"]]
    assert len(current_plans) == 1
    assert current_plans[0]["plan"] == "free"
    await db_session.close()


@pytest.mark.asyncio
async def test_list_plans_includes_prices_and_limits(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_billing_data(db_session)

    response = await client.get(
        f"/workspaces/{data['workspace'].id}/billing/plans",
        headers=_auth_headers(data["admin"]),
    )

    assert response.status_code == 200
    plans = {p["plan"]: p for p in response.json()}

    assert plans["free"]["price_monthly"] == 0
    assert plans["pro"]["price_monthly"] == 2490
    assert plans["business"]["price_monthly"] == 7490

    assert plans["free"]["limits"]["members"] == 5
    assert plans["pro"]["limits"]["members"] == 50
    assert plans["business"]["limits"]["members"] is None

    assert plans["free"]["limits"]["crypto"] is True
    assert plans["pro"]["limits"]["crypto"] is True
    await db_session.close()


# ---------------------------------------------------------------------------
# PATCH /workspaces/{id}/billing/admin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_override_upgrades_plan(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_billing_data(db_session)

    response = await client.patch(
        f"/workspaces/{data['workspace'].id}/billing/admin",
        json={"plan": "pro", "billing_period": "monthly"},
        headers=_auth_headers(data["super_admin"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"] == "pro"
    assert body["subscription"] is not None
    assert body["subscription"]["plan"] == "pro"
    assert body["subscription"]["status"] == "active"
    assert body["subscription"]["provider"] == "manual"
    assert len(body["recent_payments"]) == 1
    assert float(body["recent_payments"][0]["amount"]) == 2490.0
    await db_session.close()


@pytest.mark.asyncio
async def test_admin_override_to_free_cancels_subscription(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_billing_data(db_session)
    workspace = data["workspace"]

    now = datetime.now(UTC)
    subscription = WorkspaceSubscription(
        workspace_id=workspace.id,
        plan=WorkspacePlan.PRO,
        billing_period=BillingPeriod.MONTHLY,
        status=SubscriptionStatus.ACTIVE,
        started_at=now,
        expires_at=now + timedelta(days=30),
        auto_renew=True,
    )
    workspace.plan = WorkspacePlan.PRO
    db_session.add(subscription)
    await db_session.commit()

    response = await client.patch(
        f"/workspaces/{workspace.id}/billing/admin",
        json={"plan": "free"},
        headers=_auth_headers(data["super_admin"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"] == "free"
    assert body["subscription"] is None
    await db_session.close()


@pytest.mark.asyncio
async def test_admin_override_requires_super_admin(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_billing_data(db_session)

    response = await client.patch(
        f"/workspaces/{data['workspace'].id}/billing/admin",
        json={"plan": "pro", "billing_period": "monthly"},
        headers=_auth_headers(data["admin"]),
    )

    assert response.status_code == 403
    await db_session.close()


@pytest.mark.asyncio
async def test_admin_override_with_custom_expires_at(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_billing_data(db_session)
    custom_expiry = (datetime.now(UTC) + timedelta(days=90)).isoformat()

    response = await client.patch(
        f"/workspaces/{data['workspace'].id}/billing/admin",
        json={"plan": "business", "billing_period": "annual", "expires_at": custom_expiry},
        headers=_auth_headers(data["super_admin"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"] == "business"
    assert body["subscription"]["billing_period"] == "annual"
    await db_session.close()
