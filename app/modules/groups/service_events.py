from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select

from app.models.enums import (
    GroupEventStatus,
    GroupHistoryEventType,
    WorkspaceEventResponse,
    WorkspaceRole,
)
from app.models.group_event import GroupEvent
from app.models.user import User
from app.models.workspace_event import WorkspaceEvent
from app.models.workspace_event_group import WorkspaceEventGroup
from app.models.workspace_event_participant import WorkspaceEventParticipant
from app.modules.groups.schemas import (
    EventsFeedResponse,
    FeedEventOut,
    GroupEventCreateRequest,
    GroupEventOut,
    GroupEventUpdateRequest,
    GroupFeedEventOut,
    ParticipantSummaryOut,
    WorkspaceFeedEventOut,
)
from app.modules.groups.service_base import ActorRole, GroupsServiceBase


class GroupsEventsMixin(GroupsServiceBase):
    async def list_events(
        self,
        workspace_id: UUID,
        group_id: UUID,
        current_user: User,
        status_filter: GroupEventStatus | None = None,
    ) -> list[GroupEventOut]:
        await self._require_group_read_access(workspace_id, group_id, current_user)
        stmt = select(GroupEvent).where(GroupEvent.group_id == group_id)
        if status_filter is not None:
            stmt = stmt.where(GroupEvent.status == status_filter)
        stmt = stmt.order_by(GroupEvent.date.asc())
        result = await self.session.scalars(stmt)
        return [GroupEventOut.model_validate(item) for item in result.all()]

    async def get_events_feed(
        self,
        workspace_id: UUID,
        group_id: UUID,
        current_user: User,
        status_filter: GroupEventStatus | None = None,
        type_filter: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> EventsFeedResponse:
        access = await self._require_group_read_access(workspace_id, group_id, current_user)
        items: list[FeedEventOut] = []

        if type_filter in {None, "group"}:
            items.extend(
                await self._fetch_group_feed_events(
                    group_id,
                    status_filter=status_filter,
                    from_date=from_date,
                    to_date=to_date,
                )
            )

        if type_filter in {None, "workspace"}:
            items.extend(
                await self._fetch_workspace_feed_events(
                    group_id,
                    current_user,
                    access.actor_role,
                    status_filter=status_filter,
                    from_date=from_date,
                    to_date=to_date,
                )
            )

        reverse = status_filter in {
            GroupEventStatus.COMPLETED,
            GroupEventStatus.CANCELLED,
        }
        items.sort(key=lambda item: item.date, reverse=reverse)
        return EventsFeedResponse(items=items, total=len(items))

    async def create_event(
        self,
        workspace_id: UUID,
        group_id: UUID,
        current_user: User,
        payload: GroupEventCreateRequest,
    ) -> GroupEventOut:
        await self._require_group_write_access(workspace_id, group_id, current_user)
        event = GroupEvent(
            group_id=group_id,
            title=payload.title,
            description=payload.description,
            date=payload.date,
            location=payload.location,
            is_paid=payload.is_paid,
            amount=payload.amount,
            currency=payload.currency,
            due_date=payload.due_date,
            created_by_user_id=current_user.id,
        )
        self.session.add(event)
        await self.session.flush()
        await self._record_history(
            group_id=group_id,
            actor_user_id=current_user.id,
            event_type=GroupHistoryEventType.EVENT_CREATED,
            payload={
                "event_id": str(event.id),
                "title": event.title,
                "date": self._dt(event.date),
                "location": event.location,
                "is_paid": event.is_paid,
                "amount": self._decimal(event.amount) if event.amount is not None else None,
                "currency": event.currency,
                "due_date": self._dt(event.due_date),
            },
        )
        await self.session.commit()
        await self.session.refresh(event)
        return GroupEventOut.model_validate(event)

    async def update_event(
        self,
        workspace_id: UUID,
        group_id: UUID,
        event_id: UUID,
        current_user: User,
        payload: GroupEventUpdateRequest,
    ) -> GroupEventOut:
        await self._require_group_write_access(workspace_id, group_id, current_user)
        event = await self.session.scalar(
            select(GroupEvent).where(
                GroupEvent.id == event_id,
                GroupEvent.group_id == group_id,
            )
        )
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group event not found",
            )

        previous_status = event.status
        next_is_paid = event.is_paid if payload.is_paid is None else payload.is_paid
        next_amount = event.amount if "amount" not in payload.model_fields_set else payload.amount
        next_currency = (
            event.currency if "currency" not in payload.model_fields_set else payload.currency
        )
        next_due_date = (
            event.due_date if "due_date" not in payload.model_fields_set else payload.due_date
        )
        self._validate_event_payment(next_is_paid, next_amount, next_currency, next_due_date)

        if payload.title is not None:
            event.title = payload.title
        if "description" in payload.model_fields_set:
            event.description = payload.description
        if payload.date is not None:
            event.date = payload.date
        if "location" in payload.model_fields_set:
            event.location = payload.location
        if payload.is_paid is not None:
            event.is_paid = payload.is_paid
        if "amount" in payload.model_fields_set:
            event.amount = payload.amount
        if "currency" in payload.model_fields_set:
            event.currency = payload.currency
        if "due_date" in payload.model_fields_set:
            event.due_date = payload.due_date
        if payload.status is not None:
            event.status = payload.status

        if (
            previous_status != GroupEventStatus.CANCELLED
            and event.status == GroupEventStatus.CANCELLED
        ):
            await self._record_history(
                group_id=group_id,
                actor_user_id=current_user.id,
                event_type=GroupHistoryEventType.EVENT_CANCELLED,
                payload={
                    "event_id": str(event.id),
                    "title": event.title,
                },
            )

        await self.session.commit()
        await self.session.refresh(event)
        return GroupEventOut.model_validate(event)

    async def delete_event(
        self,
        workspace_id: UUID,
        group_id: UUID,
        event_id: UUID,
        current_user: User,
    ) -> None:
        await self._require_group_write_access(workspace_id, group_id, current_user)
        event = await self.session.scalar(
            select(GroupEvent).where(
                GroupEvent.id == event_id,
                GroupEvent.group_id == group_id,
            )
        )
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group event not found",
            )
        await self.session.delete(event)
        await self.session.commit()

    async def _fetch_group_feed_events(
        self,
        group_id: UUID,
        status_filter: GroupEventStatus | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[GroupFeedEventOut]:
        stmt = select(GroupEvent).where(GroupEvent.group_id == group_id)
        if status_filter is not None:
            stmt = stmt.where(GroupEvent.status == status_filter)
        if from_date is not None:
            stmt = stmt.where(GroupEvent.date >= from_date)
        if to_date is not None:
            stmt = stmt.where(GroupEvent.date <= to_date)

        events = (await self.session.scalars(stmt)).all()
        return [
            GroupFeedEventOut(
                id=event.id,
                title=event.title,
                date=event.date,
                location=event.location,
                status=event.status,
                is_paid=event.is_paid,
                amount=event.amount,
                currency=event.currency,
            )
            for event in events
        ]

    async def _fetch_workspace_feed_events(
        self,
        group_id: UUID,
        current_user: User,
        actor_role: ActorRole,
        status_filter: GroupEventStatus | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[WorkspaceFeedEventOut]:
        stmt = (
            select(WorkspaceEvent)
            .join(
                WorkspaceEventGroup,
                WorkspaceEventGroup.workspace_event_id == WorkspaceEvent.id,
            )
            .where(WorkspaceEventGroup.group_id == group_id)
        )
        if actor_role not in {"super_admin", WorkspaceRole.WORKSPACE_ADMIN}:
            stmt = stmt.join(
                WorkspaceEventParticipant,
                (WorkspaceEventParticipant.workspace_event_id == WorkspaceEvent.id)
                & (WorkspaceEventParticipant.user_id == current_user.id),
            )
        if status_filter is not None:
            stmt = stmt.where(WorkspaceEvent.status == status_filter)
        if from_date is not None:
            stmt = stmt.where(WorkspaceEvent.date >= from_date)
        if to_date is not None:
            stmt = stmt.where(WorkspaceEvent.date <= to_date)

        events = (await self.session.scalars(stmt)).all()
        items: list[WorkspaceFeedEventOut] = []
        for event in events:
            my_response = None
            participants_summary = None
            if actor_role in {"super_admin", WorkspaceRole.WORKSPACE_ADMIN}:
                participants_summary = await self._workspace_event_participants_summary(event.id)
            else:
                participant = await self.session.scalar(
                    select(WorkspaceEventParticipant).where(
                        WorkspaceEventParticipant.workspace_event_id == event.id,
                        WorkspaceEventParticipant.user_id == current_user.id,
                    )
                )
                my_response = participant.response.value if participant is not None else None

            items.append(
                WorkspaceFeedEventOut(
                    id=event.id,
                    title=event.title,
                    date=event.date,
                    location=event.location,
                    status=event.status,
                    audience=event.audience.value,
                    my_response=my_response,
                    participants_summary=participants_summary,
                )
            )
        return items

    async def _workspace_event_participants_summary(
        self,
        event_id: UUID,
    ) -> ParticipantSummaryOut:
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
        return ParticipantSummaryOut(
            total=accepted + declined + pending,
            accepted=accepted,
            declined=declined,
            pending=pending,
        )
