from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import (
    WorkspaceEventAudience,
    WorkspaceEventResponse,
    WorkspaceEventStatus,
    WorkspaceRole,
)


class WorkspaceEventCreateRequest(BaseModel):
    title: str
    description: str | None = None
    date: datetime
    location: str | None = None
    audience: WorkspaceEventAudience
    group_ids: list[UUID] = []


class WorkspaceEventUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    date: datetime | None = None
    location: str | None = None


class WorkspaceEventGroupsRequest(BaseModel):
    group_ids: list[UUID]


class WorkspaceEventCreatorOut(BaseModel):
    user_id: UUID
    full_name: str


class WorkspaceEventParticipantsSummaryOut(BaseModel):
    total: int
    accepted: int
    declined: int
    pending: int


class WorkspaceEventOut(BaseModel):
    id: UUID
    title: str
    description: str | None
    date: datetime
    location: str | None
    audience: WorkspaceEventAudience
    status: WorkspaceEventStatus
    created_by: WorkspaceEventCreatorOut
    created_at: datetime
    group_ids: list[UUID]
    participants_summary: WorkspaceEventParticipantsSummaryOut | None = None
    my_response: WorkspaceEventResponse | None = None


class WorkspaceEventParticipantOut(BaseModel):
    user_id: UUID
    full_name: str
    role: WorkspaceRole
    response: WorkspaceEventResponse
    responded_at: datetime | None


class WorkspaceEventResponseOut(BaseModel):
    response: WorkspaceEventResponse


class WorkspaceEventGroupIdsOut(BaseModel):
    group_ids: list[UUID]
