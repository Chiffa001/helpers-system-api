from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from app.models.enums import WorkspaceRole
from app.models.user import User
from app.models.workspace_event_participant import WorkspaceEventParticipant
from app.modules.workspace_events.service_base import (
    WorkspaceEventAccessContext,
    WorkspaceEventsServiceBase,
)
from app.modules.workspace_events.sync import audiences_for_role


class WorkspaceEventsAccessMixin(WorkspaceEventsServiceBase):
    async def _get_event_access(
        self,
        event_id: UUID,
        current_user: User,
        require_admin: bool = False,
    ) -> WorkspaceEventAccessContext:
        event = await self._get_event_or_404(event_id)
        actor_role, workspace_member = await self._get_workspace_actor(
            event.workspace_id,
            current_user,
        )
        if require_admin and actor_role not in {
            "super_admin",
            WorkspaceRole.WORKSPACE_ADMIN,
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient workspace permissions",
            )

        if actor_role in {"super_admin", WorkspaceRole.WORKSPACE_ADMIN}:
            return WorkspaceEventAccessContext(
                event=event,
                actor_role=actor_role,
                workspace_member=workspace_member,
                participant=None,
            )

        if workspace_member is None or event.audience not in audiences_for_role(
            workspace_member.role
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="access denied",
            )

        participant = await self.session.scalar(
            select(WorkspaceEventParticipant).where(
                WorkspaceEventParticipant.workspace_event_id == event.id,
                WorkspaceEventParticipant.user_id == current_user.id,
            )
        )
        if participant is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="access denied",
            )

        return WorkspaceEventAccessContext(
            event=event,
            actor_role=workspace_member.role,
            workspace_member=workspace_member,
            participant=participant,
        )

    async def _get_participant_access(
        self,
        event_id: UUID,
        current_user: User,
    ) -> WorkspaceEventAccessContext:
        event = await self._get_event_or_404(event_id)
        actor_role, workspace_member = await self._get_workspace_actor(
            event.workspace_id,
            current_user,
        )

        if workspace_member is not None and event.audience not in audiences_for_role(
            workspace_member.role
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="access denied",
            )

        participant = await self.session.scalar(
            select(WorkspaceEventParticipant).where(
                WorkspaceEventParticipant.workspace_event_id == event.id,
                WorkspaceEventParticipant.user_id == current_user.id,
            )
        )
        if participant is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="access denied",
            )

        return WorkspaceEventAccessContext(
            event=event,
            actor_role=actor_role,
            workspace_member=workspace_member,
            participant=participant,
        )
