from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import WorkspacePlan, WorkspaceRole, WorkspaceStatus


class WorkspaceOut(BaseModel):
    id: UUID
    title: str
    slug: str
    status: WorkspaceStatus
    plan: WorkspacePlan
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceCreateRequest(BaseModel):
    title: str
    slug: str
    admin_telegram_id: int | None = None


class WorkspaceUpdateRequest(BaseModel):
    title: str | None = None
    status: WorkspaceStatus | None = None


class WorkspaceMembersCount(BaseModel):
    workspace_admin: int = 0
    assistant: int = 0
    client: int = 0


class WorkspaceDetailResponse(WorkspaceOut):
    fee_rate: Decimal
    members_count: WorkspaceMembersCount


class WorkspaceMemberUser(BaseModel):
    id: UUID
    full_name: str
    username: str | None


class WorkspaceMemberResponse(BaseModel):
    id: UUID
    user: WorkspaceMemberUser
    role: WorkspaceRole
    is_active: bool
    joined_at: datetime


class WorkspaceUserResponse(BaseModel):
    id: UUID
    full_name: str
    username: str | None
    role: WorkspaceRole
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMemberCreateRequest(BaseModel):
    telegram_id: int
    role: WorkspaceRole


class WorkspaceMemberUpdateRequest(BaseModel):
    role: WorkspaceRole | None = None
    is_active: bool | None = None
