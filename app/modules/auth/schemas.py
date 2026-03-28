from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import WorkspacePlan, WorkspaceRole, WorkspaceStatus


class TelegramAuthRequest(BaseModel):
    init_data: str


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


class UserWorkspaceInfo(BaseModel):
    id: UUID
    title: str
    slug: str
    status: WorkspaceStatus
    plan: WorkspacePlan


class UserWorkspaceResponse(BaseModel):
    workspace: UserWorkspaceInfo
    role: WorkspaceRole
