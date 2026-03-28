from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.middleware.auth import get_current_user, require_super_admin
from app.middleware.workspace import WorkspaceAccessContext, require_workspace_access
from app.models.enums import WorkspaceRole, WorkspaceStatus
from app.models.user import User
from app.modules.workspaces.schemas import (
    WorkspaceCreateRequest,
    WorkspaceDetailResponse,
    WorkspaceMemberCreateRequest,
    WorkspaceMemberResponse,
    WorkspaceMemberUpdateRequest,
    WorkspaceOut,
    WorkspaceUpdateRequest,
)
from app.modules.workspaces.service import WorkspacesService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get(
    "",
    response_model=list[WorkspaceOut],
    summary="List workspaces",
    description="Returns all workspaces for super admins, or only member workspaces for regular users.",
)
async def list_workspaces(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspacesService, Depends(WorkspacesService)],
    status_filter: Annotated[WorkspaceStatus | None, Query(alias="status")] = None,
) -> list[WorkspaceOut]:
    """List workspaces visible to the current user."""
    return await service.list_workspaces(current_user, status_filter)


@router.post(
    "",
    response_model=WorkspaceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create workspace",
    description="Creates a new workspace. Available only to super admins.",
)
async def create_workspace(
    payload: WorkspaceCreateRequest,
    current_user: Annotated[User, Depends(require_super_admin)],
    service: Annotated[WorkspacesService, Depends(WorkspacesService)],
) -> WorkspaceOut:
    """Create a new workspace entry."""
    return await service.create_workspace(payload, current_user)


@router.get(
    "/{id}",
    response_model=WorkspaceDetailResponse,
    summary="Get workspace details",
    description="Returns detailed workspace data and active member counts for an accessible workspace.",
)
async def get_workspace(
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[WorkspacesService, Depends(WorkspacesService)],
) -> WorkspaceDetailResponse:
    """Return a workspace with aggregated member counts."""
    return await service.get_workspace_detail(access.workspace)


@router.patch(
    "/{id}",
    response_model=WorkspaceOut,
    summary="Update workspace",
    description="Updates workspace title or status. Available to workspace admins and super admins.",
)
async def update_workspace(
    payload: WorkspaceUpdateRequest,
    access: Annotated[
        WorkspaceAccessContext,
        Depends(require_workspace_access(WorkspaceRole.WORKSPACE_ADMIN)),
    ],
    service: Annotated[WorkspacesService, Depends(WorkspacesService)],
) -> WorkspaceOut:
    """Update mutable workspace fields."""
    return await service.update_workspace(access.workspace, payload)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workspace",
    description="Deletes a workspace. Available only to super admins.",
)
async def delete_workspace(
    id: UUID,
    current_user: Annotated[User, Depends(require_super_admin)],
    service: Annotated[WorkspacesService, Depends(WorkspacesService)],
) -> Response:
    """Delete a workspace and its dependent records."""
    del current_user
    await service.delete_workspace(id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{id}/members",
    response_model=list[WorkspaceMemberResponse],
    summary="List workspace members",
    description="Returns workspace members with linked user data. Available to workspace admins and super admins.",
)
async def list_workspace_members(
    id: UUID,
    access: Annotated[
        WorkspaceAccessContext,
        Depends(require_workspace_access(WorkspaceRole.WORKSPACE_ADMIN)),
    ],
    service: Annotated[WorkspacesService, Depends(WorkspacesService)],
) -> list[WorkspaceMemberResponse]:
    """List members of a workspace."""
    del access
    return await service.list_members(id)


@router.post(
    "/{id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add workspace member",
    description="Adds an existing user to a workspace or reactivates an inactive membership.",
)
async def add_workspace_member(
    id: UUID,
    payload: WorkspaceMemberCreateRequest,
    access: Annotated[
        WorkspaceAccessContext,
        Depends(require_workspace_access(WorkspaceRole.WORKSPACE_ADMIN)),
    ],
    service: Annotated[WorkspacesService, Depends(WorkspacesService)],
) -> WorkspaceMemberResponse:
    """Create or reactivate a workspace membership."""
    del access
    return await service.add_member(id, payload)


@router.patch(
    "/{id}/members/{user_id}",
    response_model=WorkspaceMemberResponse,
    summary="Update workspace member",
    description="Changes member role or active flag within a workspace.",
)
async def update_workspace_member(
    id: UUID,
    user_id: UUID,
    payload: WorkspaceMemberUpdateRequest,
    access: Annotated[
        WorkspaceAccessContext,
        Depends(require_workspace_access(WorkspaceRole.WORKSPACE_ADMIN)),
    ],
    service: Annotated[WorkspacesService, Depends(WorkspacesService)],
) -> WorkspaceMemberResponse:
    """Update role or status of a workspace member."""
    del access
    return await service.update_member(id, user_id, payload)


@router.delete(
    "/{id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove workspace member",
    description="Soft-removes a member from a workspace by marking the membership inactive.",
)
async def remove_workspace_member(
    id: UUID,
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[
        WorkspaceAccessContext,
        Depends(require_workspace_access(WorkspaceRole.WORKSPACE_ADMIN)),
    ],
    service: Annotated[WorkspacesService, Depends(WorkspacesService)],
) -> Response:
    """Deactivate a workspace membership."""
    del access
    await service.deactivate_member(id, user_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
