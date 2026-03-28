from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.middleware.auth import get_current_user
from app.models.enums import WorkspaceRole
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember

WorkspaceActorRole = WorkspaceRole | Literal["super_admin"]


@dataclass(slots=True)
class WorkspaceAccessContext:
    workspace: Workspace
    role: WorkspaceActorRole


def require_workspace_access(
    *allowed_roles: WorkspaceRole,
) -> Callable[..., Coroutine[Any, Any, WorkspaceAccessContext]]:
    """Validate membership in a workspace and optionally enforce allowed roles."""

    async def dependency(
        request: Request,
        id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> WorkspaceAccessContext:
        # Super admins bypass membership checks for any workspace.
        workspace = await session.get(Workspace, id)
        if workspace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        if current_user.is_super_admin:
            request.state.workspace_role = "super_admin"
            return WorkspaceAccessContext(workspace=workspace, role="super_admin")

        member = await session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == id,
                WorkspaceMember.user_id == current_user.id,
                WorkspaceMember.is_active.is_(True),
            )
        )
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workspace access denied",
            )

        if allowed_roles and member.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient workspace permissions",
            )

        # Store the resolved role for downstream request handling if needed.
        request.state.workspace_role = member.role.value
        return WorkspaceAccessContext(workspace=workspace, role=member.role)

    return dependency
