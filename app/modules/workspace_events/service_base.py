from dataclasses import dataclass
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.enums import WorkspaceEventAudience, WorkspaceRole
from app.models.group import Group
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_event import WorkspaceEvent
from app.models.workspace_event_participant import WorkspaceEventParticipant
from app.models.workspace_member import WorkspaceMember

ActorRole = Literal["super_admin"] | WorkspaceRole


@dataclass(slots=True)
class WorkspaceEventAccessContext:
    event: WorkspaceEvent
    actor_role: ActorRole
    workspace_member: WorkspaceMember | None
    participant: WorkspaceEventParticipant | None


class WorkspaceEventsServiceBase:
    def __init__(
        self,
        session: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> None:
        self.session = session

    async def _ensure_workspace_exists(self, workspace_id: UUID) -> Workspace:
        workspace = await self.session.get(Workspace, workspace_id)
        if workspace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        return workspace

    async def _get_event_or_404(self, event_id: UUID) -> WorkspaceEvent:
        event = await self.session.get(WorkspaceEvent, event_id)
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace event not found",
            )
        return event

    async def _get_workspace_actor(
        self,
        workspace_id: UUID,
        current_user: User,
    ) -> tuple[ActorRole, WorkspaceMember | None]:
        if current_user.is_super_admin:
            return "super_admin", None

        member = await self.session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user.id,
                WorkspaceMember.is_active.is_(True),
            )
        )
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workspace access denied",
            )
        return member.role, member

    async def _require_workspace_admin(
        self,
        workspace_id: UUID,
        current_user: User,
    ) -> tuple[ActorRole, WorkspaceMember | None]:
        actor_role, workspace_member = await self._get_workspace_actor(
            workspace_id,
            current_user,
        )
        if actor_role not in {"super_admin", WorkspaceRole.WORKSPACE_ADMIN}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient workspace permissions",
            )
        return actor_role, workspace_member

    async def _validate_group_ids(
        self,
        workspace_id: UUID,
        group_ids: list[UUID],
    ) -> list[UUID]:
        unique_group_ids = list(dict.fromkeys(group_ids))
        if not unique_group_ids:
            return []

        existing_ids = set(
            (
                await self.session.scalars(
                    select(Group.id).where(
                        Group.workspace_id == workspace_id,
                        Group.id.in_(unique_group_ids),
                    )
                )
            ).all()
        )
        missing_group_ids = [
            group_id for group_id in unique_group_ids if group_id not in existing_ids
        ]
        if missing_group_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="group not found in workspace",
            )
        return unique_group_ids

    def _roles_for_audience(
        self,
        audience: WorkspaceEventAudience,
    ) -> tuple[WorkspaceRole, ...]:
        if audience == WorkspaceEventAudience.ADMINS:
            return (WorkspaceRole.WORKSPACE_ADMIN,)
        if audience == WorkspaceEventAudience.ASSISTANTS:
            return (WorkspaceRole.ASSISTANT,)
        return (
            WorkspaceRole.WORKSPACE_ADMIN,
            WorkspaceRole.ASSISTANT,
            WorkspaceRole.CLIENT,
        )
