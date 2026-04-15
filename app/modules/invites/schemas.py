from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import WorkspaceRole

INVITE_TTL_DAYS = 7


class WorkspaceInviteCreateRequest(BaseModel):
    role: WorkspaceRole
    group_id: UUID | None = None


class WorkspaceInviteResponse(BaseModel):
    id: UUID
    token: UUID
    role: WorkspaceRole
    group_id: UUID | None
    expires_at: datetime
    invite_url: str


class WorkspaceInvitePublicResponse(BaseModel):
    workspace_title: str
    role: WorkspaceRole
    group_id: UUID | None
    expires_at: datetime


class WorkspaceInviteAcceptResponse(BaseModel):
    workspace_id: UUID
    workspace_title: str
    role: WorkspaceRole


def default_invite_expiration() -> datetime:
    return datetime.now(UTC) + timedelta(days=INVITE_TTL_DAYS)
