from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.middleware.auth import get_current_user
from app.middleware.workspace import WorkspaceAccessContext, require_workspace_access
from app.models.enums import (
    WorkspaceEventAudience,
    WorkspaceEventResponse,
    WorkspaceEventStatus,
    WorkspaceRole,
)
from app.models.user import User
from app.modules.workspace_events.schemas import (
    WorkspaceEventCreateRequest,
    WorkspaceEventGroupIdsOut,
    WorkspaceEventGroupsRequest,
    WorkspaceEventOut,
    WorkspaceEventParticipantOut,
    WorkspaceEventResponseOut,
    WorkspaceEventUpdateRequest,
)
from app.modules.workspace_events.service import WorkspaceEventsService

workspace_router = APIRouter(prefix="/workspaces", tags=["workspace-events"])
router = APIRouter(tags=["workspace-events"])


@workspace_router.get(
    "/{id}/events",
    response_model=list[WorkspaceEventOut],
    summary="List workspace events",
)
async def list_workspace_events(
    id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[WorkspaceEventsService, Depends(WorkspaceEventsService)],
    status_filter: Annotated[WorkspaceEventStatus | None, Query(alias="status")] = None,
    audience: Annotated[WorkspaceEventAudience | None, Query()] = None,
    group_id: Annotated[UUID | None, Query()] = None,
    from_date: Annotated[datetime | None, Query()] = None,
    to_date: Annotated[datetime | None, Query()] = None,
) -> list[WorkspaceEventOut]:
    del access
    return await service.list_events(
        workspace_id=id,
        current_user=current_user,
        status_filter=status_filter,
        audience=audience,
        group_id=group_id,
        from_date=from_date,
        to_date=to_date,
    )


@workspace_router.post(
    "/{id}/events",
    response_model=WorkspaceEventOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create workspace event",
)
async def create_workspace_event(
    id: UUID,
    payload: WorkspaceEventCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[
        WorkspaceAccessContext,
        Depends(require_workspace_access(WorkspaceRole.WORKSPACE_ADMIN)),
    ],
    service: Annotated[WorkspaceEventsService, Depends(WorkspaceEventsService)],
) -> WorkspaceEventOut:
    del access
    return await service.create_event(id, current_user, payload)


@router.get(
    "/workspace-events/{id}",
    response_model=WorkspaceEventOut,
    summary="Get workspace event details",
)
async def get_workspace_event(
    id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceEventsService, Depends(WorkspaceEventsService)],
) -> WorkspaceEventOut:
    return await service.get_event(id, current_user)


@router.patch(
    "/workspace-events/{id}",
    response_model=WorkspaceEventOut,
    summary="Update workspace event",
)
async def update_workspace_event(
    id: UUID,
    payload: WorkspaceEventUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceEventsService, Depends(WorkspaceEventsService)],
) -> WorkspaceEventOut:
    return await service.update_event(id, current_user, payload)


@router.post(
    "/workspace-events/{id}/complete",
    response_model=WorkspaceEventOut,
    summary="Complete workspace event",
)
async def complete_workspace_event(
    id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceEventsService, Depends(WorkspaceEventsService)],
) -> WorkspaceEventOut:
    return await service.complete_event(id, current_user)


@router.post(
    "/workspace-events/{id}/cancel",
    response_model=WorkspaceEventOut,
    summary="Cancel workspace event",
)
async def cancel_workspace_event(
    id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceEventsService, Depends(WorkspaceEventsService)],
) -> WorkspaceEventOut:
    return await service.cancel_event(id, current_user)


@router.delete(
    "/workspace-events/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workspace event",
)
async def delete_workspace_event(
    id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceEventsService, Depends(WorkspaceEventsService)],
) -> Response:
    await service.delete_event(id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/workspace-events/{id}/accept",
    response_model=WorkspaceEventResponseOut,
    summary="Accept workspace event",
)
async def accept_workspace_event(
    id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceEventsService, Depends(WorkspaceEventsService)],
) -> WorkspaceEventResponseOut:
    return await service.accept_event(id, current_user)


@router.post(
    "/workspace-events/{id}/decline",
    response_model=WorkspaceEventResponseOut,
    summary="Decline workspace event",
)
async def decline_workspace_event(
    id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceEventsService, Depends(WorkspaceEventsService)],
) -> WorkspaceEventResponseOut:
    return await service.decline_event(id, current_user)


@router.get(
    "/workspace-events/{id}/participants",
    response_model=list[WorkspaceEventParticipantOut],
    summary="List workspace event participants",
)
async def list_workspace_event_participants(
    id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceEventsService, Depends(WorkspaceEventsService)],
    response: Annotated[WorkspaceEventResponse | None, Query()] = None,
) -> list[WorkspaceEventParticipantOut]:
    return await service.list_participants(id, current_user, response)


@router.post(
    "/workspace-events/{id}/groups",
    response_model=WorkspaceEventGroupIdsOut,
    summary="Add workspace event groups",
)
async def add_workspace_event_groups(
    id: UUID,
    payload: WorkspaceEventGroupsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceEventsService, Depends(WorkspaceEventsService)],
) -> WorkspaceEventGroupIdsOut:
    return await service.add_groups(id, current_user, payload.group_ids)


@router.delete(
    "/workspace-events/{id}/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove workspace event group",
)
async def remove_workspace_event_group(
    id: UUID,
    group_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceEventsService, Depends(WorkspaceEventsService)],
) -> Response:
    await service.remove_group(id, current_user, group_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
