from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.enums import WorkspacePlan, WorkspaceRole, WorkspaceStatus


class CurrentUserResponse(BaseModel):
    id: UUID
    full_name: str
    username: str | None
    is_super_admin: bool

    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: CurrentUserResponse


class TelegramWebAppUser(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


class TelegramAuthRequest(BaseModel):
    workspace_slug: str | None = None
    user: TelegramWebAppUser
    auth_date: int
    hash: str
    query_id: str | None = None

    @field_validator("auth_date", mode="before")
    @classmethod
    def parse_auth_date(cls, v: object) -> int:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return int(dt.astimezone(UTC).timestamp())
        if isinstance(v, (int, float)):
            return int(v)
        raise ValueError(f"Cannot parse auth_date: {v!r}")


class UserWorkspaceInfo(BaseModel):
    id: UUID
    title: str
    slug: str
    status: WorkspaceStatus
    plan: WorkspacePlan


class UserWorkspaceResponse(BaseModel):
    workspace: UserWorkspaceInfo
    role: WorkspaceRole
