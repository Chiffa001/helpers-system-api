from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.middleware.auth import get_current_user
from app.middleware.workspace import WorkspaceAccessContext, require_workspace_access
from app.models.enums import (
    GroupEventStatus,
    GroupStageStatus,
    GroupStatus,
    InvoiceStatus,
    WorkspaceRole,
)
from app.models.user import User
from app.modules.groups.schemas import (
    EventsFeedResponse,
    GroupCreateRequest,
    GroupDocumentCreateRequest,
    GroupDocumentOut,
    GroupEventCreateRequest,
    GroupEventOut,
    GroupEventUpdateRequest,
    GroupFavoriteResponse,
    GroupHistoryEntryOut,
    GroupMemberCreateRequest,
    GroupMemberResponse,
    GroupOut,
    GroupStageCreateRequest,
    GroupStageOut,
    GroupStageUpdateRequest,
    GroupUpdateRequest,
    InvoiceCreateRequest,
    InvoiceOut,
    InvoicePayRequest,
    InvoiceUpdateRequest,
)
from app.modules.groups.service import GroupsService

router = APIRouter(prefix="/workspaces", tags=["groups"])
favorites_router = APIRouter(tags=["groups"])


@router.get(
    "/{id}/groups",
    response_model=list[GroupOut],
    summary="List groups",
)
async def list_groups(
    id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
    status_filter: Annotated[GroupStatus | None, Query(alias="status")] = None,
) -> list[GroupOut]:
    del id
    return await service.list_groups(access.workspace, current_user, status_filter)


@router.post(
    "/{id}/groups",
    response_model=GroupOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create group",
)
async def create_group(
    payload: GroupCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[
        WorkspaceAccessContext,
        Depends(require_workspace_access(WorkspaceRole.WORKSPACE_ADMIN)),
    ],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> GroupOut:
    return await service.create_group(access.workspace, current_user, payload)


@router.patch(
    "/{id}/groups/{group_id}",
    response_model=GroupOut,
    summary="Update group",
)
async def update_group(
    id: UUID,
    group_id: UUID,
    payload: GroupUpdateRequest,
    access: Annotated[
        WorkspaceAccessContext,
        Depends(require_workspace_access(WorkspaceRole.WORKSPACE_ADMIN)),
    ],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> GroupOut:
    del access
    return await service.update_group(id, group_id, payload)


@router.get(
    "/{id}/groups/{group_id}/members",
    response_model=list[GroupMemberResponse],
    summary="List group members",
)
async def list_group_members(
    id: UUID,
    group_id: UUID,
    access: Annotated[
        WorkspaceAccessContext,
        Depends(require_workspace_access(WorkspaceRole.WORKSPACE_ADMIN)),
    ],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> list[GroupMemberResponse]:
    del access
    return await service.list_members(id, group_id)


@router.post(
    "/{id}/groups/{group_id}/members",
    response_model=GroupMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add group member",
)
async def add_group_member(
    id: UUID,
    group_id: UUID,
    payload: GroupMemberCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[
        WorkspaceAccessContext,
        Depends(require_workspace_access(WorkspaceRole.WORKSPACE_ADMIN)),
    ],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> GroupMemberResponse:
    del access
    return await service.add_member(id, group_id, payload, actor=current_user)


@router.delete(
    "/{id}/groups/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove group member",
)
async def remove_group_member(
    id: UUID,
    group_id: UUID,
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[
        WorkspaceAccessContext,
        Depends(require_workspace_access(WorkspaceRole.WORKSPACE_ADMIN)),
    ],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> Response:
    del access
    await service.remove_member(id, group_id, user_id, actor=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{id}/groups/{group_id}/documents",
    response_model=list[GroupDocumentOut],
    summary="List group documents",
)
async def list_group_documents(
    id: UUID,
    group_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> list[GroupDocumentOut]:
    del access
    return await service.list_documents(id, group_id, current_user)


@router.post(
    "/{id}/groups/{group_id}/documents",
    response_model=GroupDocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create group document",
)
async def create_group_document(
    id: UUID,
    group_id: UUID,
    payload: GroupDocumentCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> GroupDocumentOut:
    del access
    return await service.create_document(id, group_id, current_user, payload)


@router.delete(
    "/{id}/groups/{group_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete group document",
)
async def delete_group_document(
    id: UUID,
    group_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> Response:
    del access
    await service.delete_document(id, group_id, document_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{id}/groups/{group_id}/stages",
    response_model=list[GroupStageOut],
    summary="List group stages",
)
async def list_group_stages(
    id: UUID,
    group_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
    status_filter: Annotated[GroupStageStatus | None, Query(alias="status")] = None,
) -> list[GroupStageOut]:
    del access
    return await service.list_stages(id, group_id, current_user, status_filter)


@router.post(
    "/{id}/groups/{group_id}/stages",
    response_model=GroupStageOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create group stage",
)
async def create_group_stage(
    id: UUID,
    group_id: UUID,
    payload: GroupStageCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> GroupStageOut:
    del access
    return await service.create_stage(id, group_id, current_user, payload)


@router.patch(
    "/{id}/groups/{group_id}/stages/{stage_id}",
    response_model=GroupStageOut,
    summary="Update group stage",
)
async def update_group_stage(
    id: UUID,
    group_id: UUID,
    stage_id: UUID,
    payload: GroupStageUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> GroupStageOut:
    del access
    return await service.update_stage(id, group_id, stage_id, current_user, payload)


@router.delete(
    "/{id}/groups/{group_id}/stages/{stage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete group stage",
)
async def delete_group_stage(
    id: UUID,
    group_id: UUID,
    stage_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> Response:
    del access
    await service.delete_stage(id, group_id, stage_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{id}/groups/{group_id}/events",
    response_model=list[GroupEventOut],
    summary="List group events",
)
async def list_group_events(
    id: UUID,
    group_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
    status_filter: Annotated[GroupEventStatus | None, Query(alias="status")] = None,
) -> list[GroupEventOut]:
    del access
    return await service.list_events(id, group_id, current_user, status_filter)


@router.get(
    "/{id}/groups/{group_id}/events/feed",
    response_model=EventsFeedResponse,
    summary="List aggregated group events feed",
)
async def list_group_events_feed(
    id: UUID,
    group_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
    status_filter: Annotated[GroupEventStatus | None, Query(alias="status")] = None,
    type_filter: Annotated[str | None, Query(alias="type")] = None,
    from_date: Annotated[datetime | None, Query()] = None,
    to_date: Annotated[datetime | None, Query()] = None,
) -> EventsFeedResponse:
    del access
    return await service.get_events_feed(
        id,
        group_id,
        current_user,
        status_filter=status_filter,
        type_filter=type_filter,
        from_date=from_date,
        to_date=to_date,
    )


@router.post(
    "/{id}/groups/{group_id}/events",
    response_model=GroupEventOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create group event",
)
async def create_group_event(
    id: UUID,
    group_id: UUID,
    payload: GroupEventCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> GroupEventOut:
    del access
    return await service.create_event(id, group_id, current_user, payload)


@router.patch(
    "/{id}/groups/{group_id}/events/{event_id}",
    response_model=GroupEventOut,
    summary="Update group event",
)
async def update_group_event(
    id: UUID,
    group_id: UUID,
    event_id: UUID,
    payload: GroupEventUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> GroupEventOut:
    del access
    return await service.update_event(id, group_id, event_id, current_user, payload)


@router.delete(
    "/{id}/groups/{group_id}/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete group event",
)
async def delete_group_event(
    id: UUID,
    group_id: UUID,
    event_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> Response:
    del access
    await service.delete_event(id, group_id, event_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{id}/groups/{group_id}/invoices",
    response_model=list[InvoiceOut],
    summary="List group invoices",
)
async def list_group_invoices(
    id: UUID,
    group_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
    status_filter: Annotated[InvoiceStatus | None, Query(alias="status")] = None,
) -> list[InvoiceOut]:
    del access
    return await service.list_invoices(id, group_id, current_user, status_filter)


@router.post(
    "/{id}/groups/{group_id}/invoices",
    response_model=InvoiceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create group invoice",
)
async def create_group_invoice(
    id: UUID,
    group_id: UUID,
    payload: InvoiceCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> InvoiceOut:
    del access
    return await service.create_invoice(id, group_id, current_user, payload)


@router.patch(
    "/{id}/groups/{group_id}/invoices/{invoice_id}",
    response_model=InvoiceOut,
    summary="Update group invoice",
)
async def update_group_invoice(
    id: UUID,
    group_id: UUID,
    invoice_id: UUID,
    payload: InvoiceUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> InvoiceOut:
    del access
    return await service.update_invoice(id, group_id, invoice_id, current_user, payload)


@router.post(
    "/{id}/groups/{group_id}/invoices/{invoice_id}/pay",
    response_model=InvoiceOut,
    summary="Start invoice payment",
)
async def pay_group_invoice(
    id: UUID,
    group_id: UUID,
    invoice_id: UUID,
    payload: InvoicePayRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> InvoiceOut:
    del access
    return await service.pay_invoice(id, group_id, invoice_id, current_user, payload)


@router.get(
    "/{id}/groups/{group_id}/history",
    response_model=list[GroupHistoryEntryOut],
    summary="List group history",
)
async def list_group_history(
    id: UUID,
    group_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    access: Annotated[WorkspaceAccessContext, Depends(require_workspace_access())],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> list[GroupHistoryEntryOut]:
    del access
    return await service.list_history(id, group_id, current_user)


@favorites_router.post(
    "/groups/{id}/favorite",
    response_model=GroupFavoriteResponse,
    summary="Favorite group",
)
async def favorite_group(
    id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> GroupFavoriteResponse:
    return await service.favorite_group(id, current_user)


@favorites_router.delete(
    "/groups/{id}/favorite",
    response_model=GroupFavoriteResponse,
    summary="Unfavorite group",
)
async def unfavorite_group(
    id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[GroupsService, Depends(GroupsService)],
) -> GroupFavoriteResponse:
    return await service.unfavorite_group(id, current_user)
