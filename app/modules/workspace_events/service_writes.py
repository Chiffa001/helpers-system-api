from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from app.models.enums import WorkspaceEventResponse, WorkspaceEventStatus
from app.models.user import User
from app.models.workspace_event import WorkspaceEvent
from app.models.workspace_event_group import WorkspaceEventGroup
from app.models.workspace_event_participant import WorkspaceEventParticipant
from app.models.workspace_member import WorkspaceMember
from app.modules.workspace_events.schemas import (
    WorkspaceEventCreateRequest,
    WorkspaceEventGroupIdsOut,
    WorkspaceEventOut,
    WorkspaceEventResponseOut,
    WorkspaceEventUpdateRequest,
)
from app.modules.workspace_events.service_reads import WorkspaceEventsReadsMixin


class WorkspaceEventsWritesMixin(WorkspaceEventsReadsMixin):
    async def create_event(
        self,
        workspace_id: UUID,
        current_user: User,
        payload: WorkspaceEventCreateRequest,
    ) -> WorkspaceEventOut:
        actor_role, _ = await self._require_workspace_admin(workspace_id, current_user)
        self._validate_future_date(payload.date)
        group_ids = await self._validate_group_ids(workspace_id, payload.group_ids)

        event = WorkspaceEvent(
            workspace_id=workspace_id,
            title=payload.title,
            description=payload.description,
            date=payload.date,
            location=payload.location,
            audience=payload.audience,
            created_by_user_id=current_user.id,
        )
        self.session.add(event)
        await self.session.flush()

        await self._create_participants_for_event(event)
        for group_id in group_ids:
            self.session.add(
                WorkspaceEventGroup(
                    workspace_event_id=event.id,
                    group_id=group_id,
                )
            )

        await self.session.commit()
        await self.session.refresh(event)
        return await self._build_event_out(
            event,
            actor_role=actor_role,
            current_user_id=current_user.id,
        )

    async def update_event(
        self,
        event_id: UUID,
        current_user: User,
        payload: WorkspaceEventUpdateRequest,
    ) -> WorkspaceEventOut:
        access = await self._get_event_access(event_id, current_user, require_admin=True)
        if access.event.status == WorkspaceEventStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="event is not editable",
            )
        if access.event.status != WorkspaceEventStatus.UPCOMING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="event is not editable",
            )

        if payload.title is not None:
            access.event.title = payload.title
        if "description" in payload.model_fields_set:
            access.event.description = payload.description
        if payload.date is not None:
            access.event.date = payload.date
        if "location" in payload.model_fields_set:
            access.event.location = payload.location

        await self.session.commit()
        await self.session.refresh(access.event)
        return await self._build_event_out(
            access.event,
            actor_role=access.actor_role,
            current_user_id=current_user.id,
        )

    async def complete_event(self, event_id: UUID, current_user: User) -> WorkspaceEventOut:
        return await self._set_status(event_id, current_user, WorkspaceEventStatus.COMPLETED)

    async def cancel_event(self, event_id: UUID, current_user: User) -> WorkspaceEventOut:
        return await self._set_status(event_id, current_user, WorkspaceEventStatus.CANCELLED)

    async def delete_event(self, event_id: UUID, current_user: User) -> None:
        access = await self._get_event_access(event_id, current_user, require_admin=True)
        if access.event.status != WorkspaceEventStatus.UPCOMING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="only upcoming events can be deleted",
            )
        await self.session.delete(access.event)
        await self.session.commit()

    async def accept_event(
        self,
        event_id: UUID,
        current_user: User,
    ) -> WorkspaceEventResponseOut:
        return await self._set_response(event_id, current_user, WorkspaceEventResponse.ACCEPTED)

    async def decline_event(
        self,
        event_id: UUID,
        current_user: User,
    ) -> WorkspaceEventResponseOut:
        return await self._set_response(event_id, current_user, WorkspaceEventResponse.DECLINED)

    async def add_groups(
        self,
        event_id: UUID,
        current_user: User,
        group_ids: list[UUID],
    ) -> WorkspaceEventGroupIdsOut:
        access = await self._get_event_access(event_id, current_user, require_admin=True)
        validated_group_ids = await self._validate_group_ids(access.event.workspace_id, group_ids)
        existing_group_ids = set(
            (
                await self.session.scalars(
                    select(WorkspaceEventGroup.group_id).where(
                        WorkspaceEventGroup.workspace_event_id == access.event.id
                    )
                )
            ).all()
        )
        for group_id in validated_group_ids:
            if group_id in existing_group_ids:
                continue
            self.session.add(
                WorkspaceEventGroup(
                    workspace_event_id=access.event.id,
                    group_id=group_id,
                )
            )
        await self.session.commit()
        persisted_group_ids = (
            await self.session.scalars(
                select(WorkspaceEventGroup.group_id).where(
                    WorkspaceEventGroup.workspace_event_id == access.event.id
                )
            )
        ).all()
        return WorkspaceEventGroupIdsOut(
            group_ids=list(persisted_group_ids),
        )

    async def remove_group(
        self,
        event_id: UUID,
        current_user: User,
        group_id: UUID,
    ) -> None:
        await self._get_event_access(event_id, current_user, require_admin=True)
        binding = await self.session.scalar(
            select(WorkspaceEventGroup).where(
                WorkspaceEventGroup.workspace_event_id == event_id,
                WorkspaceEventGroup.group_id == group_id,
            )
        )
        if binding is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace event group binding not found",
            )
        await self.session.delete(binding)
        await self.session.commit()

    async def _set_status(
        self,
        event_id: UUID,
        current_user: User,
        next_status: WorkspaceEventStatus,
    ) -> WorkspaceEventOut:
        access = await self._get_event_access(event_id, current_user, require_admin=True)
        if access.event.status != WorkspaceEventStatus.UPCOMING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="event is not editable",
            )
        access.event.status = next_status
        await self.session.commit()
        await self.session.refresh(access.event)
        return await self._build_event_out(
            access.event,
            actor_role=access.actor_role,
            current_user_id=current_user.id,
        )

    async def _set_response(
        self,
        event_id: UUID,
        current_user: User,
        response: WorkspaceEventResponse,
    ) -> WorkspaceEventResponseOut:
        access = await self._get_participant_access(event_id, current_user)
        participant = access.participant
        if participant is None:
            raise RuntimeError("Participant access requires a workspace event participant")
        if access.event.status != WorkspaceEventStatus.UPCOMING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only upcoming workspace events can be responded to",
            )
        participant.response = response
        participant.responded_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(participant)
        return WorkspaceEventResponseOut(response=participant.response)

    async def _create_participants_for_event(self, event: WorkspaceEvent) -> None:
        members = (
            await self.session.scalars(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == event.workspace_id,
                    WorkspaceMember.is_active.is_(True),
                    WorkspaceMember.role.in_(self._roles_for_audience(event.audience)),
                )
            )
        ).all()
        for member in members:
            self.session.add(
                WorkspaceEventParticipant(
                    workspace_event_id=event.id,
                    user_id=member.user_id,
                )
            )

    def _validate_future_date(self, value: datetime) -> None:
        if value <= datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="date must be in the future",
            )
