from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.middleware.auth import get_current_user
from app.middleware.workspace import WorkspaceAccessContext, require_workspace_access
from app.models.enums import WorkspaceRole
from app.models.user import User
from app.modules.invites.schemas import (
    WorkspaceInviteAcceptResponse,
    WorkspaceInviteCreateRequest,
    WorkspaceInvitePublicResponse,
    WorkspaceInviteResponse,
)
from app.modules.invites.service import InvitesService

router = APIRouter(tags=["invites"])
workspace_router = APIRouter(prefix="/workspaces", tags=["invites"])


@workspace_router.post(
    "/{id}/invites",
    response_model=WorkspaceInviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create workspace invite",
)
async def create_workspace_invite(
    id: UUID,
    payload: WorkspaceInviteCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[
        WorkspaceAccessContext,
        Depends(require_workspace_access(WorkspaceRole.WORKSPACE_ADMIN)),
    ],
    service: Annotated[InvitesService, Depends(InvitesService)],
) -> WorkspaceInviteResponse:
    del id
    return await service.create_invite(access.workspace, current_user, payload)


@workspace_router.get(
    "/{id}/invites",
    response_model=list[WorkspaceInviteResponse],
    summary="List active workspace invites",
)
async def list_workspace_invites(
    id: UUID,
    access: Annotated[
        WorkspaceAccessContext,
        Depends(require_workspace_access(WorkspaceRole.WORKSPACE_ADMIN)),
    ],
    service: Annotated[InvitesService, Depends(InvitesService)],
) -> list[WorkspaceInviteResponse]:
    del id
    return await service.list_invites(access.workspace)


@workspace_router.delete(
    "/{id}/invites/{token}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke workspace invite",
)
async def revoke_workspace_invite(
    id: UUID,
    token: UUID,
    access: Annotated[
        WorkspaceAccessContext,
        Depends(require_workspace_access(WorkspaceRole.WORKSPACE_ADMIN)),
    ],
    service: Annotated[InvitesService, Depends(InvitesService)],
) -> Response:
    del access
    await service.revoke_invite(id, token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/invites/{token}",
    response_model=WorkspaceInvitePublicResponse,
    summary="Get invite by token",
)
async def get_invite(
    token: UUID,
    service: Annotated[InvitesService, Depends(InvitesService)],
) -> WorkspaceInvitePublicResponse:
    return await service.get_invite(token)


@router.post(
    "/invites/{token}/accept",
    response_model=WorkspaceInviteAcceptResponse,
    summary="Accept invite by token",
)
async def accept_invite(
    token: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InvitesService, Depends(InvitesService)],
) -> WorkspaceInviteAcceptResponse:
    return await service.accept_invite(token, current_user)
