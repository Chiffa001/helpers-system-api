from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select

from app.models.enums import (
    WorkspaceEventAudience,
    WorkspaceEventResponse,
    WorkspaceEventStatus,
    WorkspaceRole,
)
from app.models.user import User
from app.models.workspace_event import WorkspaceEvent
from app.models.workspace_event_group import WorkspaceEventGroup
from app.models.workspace_event_participant import WorkspaceEventParticipant
from app.models.workspace_member import WorkspaceMember
from app.modules.workspace_events.schemas import (
    WorkspaceEventCreatorOut,
    WorkspaceEventOut,
    WorkspaceEventParticipantOut,
    WorkspaceEventParticipantsSummaryOut,
)
from app.modules.workspace_events.service_access import WorkspaceEventsAccessMixin
from app.modules.workspace_events.service_base import ActorRole
from app.modules.workspace_events.sync import audiences_for_role


class WorkspaceEventsReadsMixin(WorkspaceEventsAccessMixin):
    async def list_events(
        self,
        workspace_id: UUID,
        current_user: User,
        status_filter: WorkspaceEventStatus | None = None,
        audience: WorkspaceEventAudience | None = None,
        group_id: UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[WorkspaceEventOut]:
        await self._ensure_workspace_exists(workspace_id)
        actor_role, workspace_member = await self._get_workspace_actor(
            workspace_id,
            current_user,
        )

        if audience is not None and actor_role not in {
            "super_admin",
            WorkspaceRole.WORKSPACE_ADMIN,
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Audience filter is not available for your role",
            )

        stmt = select(WorkspaceEvent).where(WorkspaceEvent.workspace_id == workspace_id)
        if status_filter is not None:
            stmt = stmt.where(WorkspaceEvent.status == status_filter)
        if audience is not None:
            stmt = stmt.where(WorkspaceEvent.audience == audience)
        if from_date is not None:
            stmt = stmt.where(WorkspaceEvent.date >= from_date)
        if to_date is not None:
            stmt = stmt.where(WorkspaceEvent.date <= to_date)
        if group_id is not None:
            stmt = stmt.join(
                WorkspaceEventGroup,
                WorkspaceEventGroup.workspace_event_id == WorkspaceEvent.id,
            ).where(WorkspaceEventGroup.group_id == group_id)
        if workspace_member is not None and workspace_member.role != WorkspaceRole.WORKSPACE_ADMIN:
            stmt = stmt.join(
                WorkspaceEventParticipant,
                WorkspaceEventParticipant.workspace_event_id == WorkspaceEvent.id,
            ).where(
                WorkspaceEventParticipant.user_id == current_user.id,
                WorkspaceEvent.audience.in_(audiences_for_role(workspace_member.role)),
            )

        order_by = WorkspaceEvent.date.asc()
        if status_filter in {
            WorkspaceEventStatus.COMPLETED,
            WorkspaceEventStatus.CANCELLED,
        }:
            order_by = WorkspaceEvent.date.desc()

        result = await self.session.scalars(stmt.order_by(order_by, WorkspaceEvent.id.asc()))
        return [
            await self._build_event_out(
                item,
                actor_role=actor_role,
                current_user_id=current_user.id,
            )
            for item in result.all()
        ]

    async def get_event(self, event_id: UUID, current_user: User) -> WorkspaceEventOut:
        access = await self._get_event_access(event_id, current_user)
        return await self._build_event_out(
            access.event,
            actor_role=access.actor_role,
            current_user_id=current_user.id,
            participant=access.participant,
        )

    async def list_participants(
        self,
        event_id: UUID,
        current_user: User,
        response: WorkspaceEventResponse | None = None,
    ) -> list[WorkspaceEventParticipantOut]:
        access = await self._get_event_access(event_id, current_user, require_admin=True)
        stmt = (
            select(WorkspaceEventParticipant, User, WorkspaceMember.role)
            .join(User, User.id == WorkspaceEventParticipant.user_id)
            .join(
                WorkspaceMember,
                (WorkspaceMember.user_id == WorkspaceEventParticipant.user_id)
                & (WorkspaceMember.workspace_id == access.event.workspace_id),
            )
            .where(WorkspaceEventParticipant.workspace_event_id == event_id)
            .order_by(User.full_name.asc(), WorkspaceEventParticipant.id.asc())
        )
        if response is not None:
            stmt = stmt.where(WorkspaceEventParticipant.response == response)

        result = await self.session.execute(stmt)
        return [
            WorkspaceEventParticipantOut(
                user_id=user.id,
                full_name=user.full_name,
                role=role,
                response=participant.response,
                responded_at=participant.responded_at,
            )
            for participant, user, role in result.all()
        ]

    async def _build_event_out(
        self,
        event: WorkspaceEvent,
        actor_role: ActorRole,
        current_user_id: UUID,
        participant: WorkspaceEventParticipant | None = None,
    ) -> WorkspaceEventOut:
        creator = await self.session.get(User, event.created_by_user_id)
        if creator is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="workspace event creator not found",
            )
        created_by = WorkspaceEventCreatorOut(
            user_id=creator.id,
            full_name=creator.full_name,
        )

        group_ids = (
            await self.session.scalars(
                select(WorkspaceEventGroup.group_id).where(
                    WorkspaceEventGroup.workspace_event_id == event.id
                )
            )
        ).all()

        participants_summary = None
        my_response = None
        if actor_role in {"super_admin", WorkspaceRole.WORKSPACE_ADMIN}:
            participants_summary = await self._get_participants_summary(event.id)
        else:
            resolved_participant = participant or await self.session.scalar(
                select(WorkspaceEventParticipant).where(
                    WorkspaceEventParticipant.workspace_event_id == event.id,
                    WorkspaceEventParticipant.user_id == current_user_id,
                )
            )
            my_response = (
                resolved_participant.response if resolved_participant is not None else None
            )

        return WorkspaceEventOut(
            id=event.id,
            title=event.title,
            description=event.description,
            date=event.date,
            location=event.location,
            audience=event.audience,
            status=event.status,
            created_by=created_by,
            created_at=event.created_at,
            group_ids=list(group_ids),
            participants_summary=participants_summary,
            my_response=my_response,
        )

    async def _get_participants_summary(
        self,
        event_id: UUID,
    ) -> WorkspaceEventParticipantsSummaryOut:
        counts = {
            response.value: count
            for response, count in (
                await self.session.execute(
                    select(
                        WorkspaceEventParticipant.response,
                        func.count(WorkspaceEventParticipant.id),
                    )
                    .where(WorkspaceEventParticipant.workspace_event_id == event_id)
                    .group_by(WorkspaceEventParticipant.response)
                )
            ).all()
        }
        accepted = counts.get(WorkspaceEventResponse.ACCEPTED.value, 0)
        declined = counts.get(WorkspaceEventResponse.DECLINED.value, 0)
        pending = counts.get(WorkspaceEventResponse.PENDING.value, 0)
        return WorkspaceEventParticipantsSummaryOut(
            total=accepted + declined + pending,
            accepted=accepted,
            declined=declined,
            pending=pending,
        )
