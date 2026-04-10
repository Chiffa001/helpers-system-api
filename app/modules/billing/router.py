from typing import Annotated

from fastapi import APIRouter, Depends

from app.middleware.auth import require_super_admin
from app.middleware.workspace import WorkspaceAccessContext, require_workspace_access
from app.models.enums import WorkspaceRole
from app.models.user import User
from app.modules.billing.schemas import (
    AdminPlanOverrideRequest,
    BillingInfoResponse,
    PlanOut,
)
from app.modules.billing.service import BillingService

router = APIRouter(prefix="/workspaces/{id}/billing", tags=["billing"])


@router.get(
    "",
    response_model=BillingInfoResponse,
    summary="Get workspace billing info",
    description="Returns current plan, active subscription, limits usage, and recent payments.",
)
async def get_billing_info(
    access: Annotated[
        WorkspaceAccessContext,
        Depends(require_workspace_access(WorkspaceRole.WORKSPACE_ADMIN)),
    ],
    service: Annotated[BillingService, Depends(BillingService)],
) -> BillingInfoResponse:
    return await service.get_billing_info(access.workspace)


@router.get(
    "/plans",
    response_model=list[PlanOut],
    summary="List available billing plans",
    description="Returns all plans with prices, limits, and whether each is the current plan.",
)
async def list_plans(
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[BillingService, Depends(BillingService)],
) -> list[PlanOut]:
    return await service.list_plans(access.workspace)


@router.patch(
    "/admin",
    response_model=BillingInfoResponse,
    summary="Admin: manually override workspace plan",
    description="Super admin only. Sets the workspace plan without payment processing.",
)
async def admin_override_plan(
    payload: AdminPlanOverrideRequest,
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    _current_user: Annotated[User, Depends(require_super_admin)],
    service: Annotated[BillingService, Depends(BillingService)],
) -> BillingInfoResponse:
    return await service.admin_override_plan(access.workspace, payload)
