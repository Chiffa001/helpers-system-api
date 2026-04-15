from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from app.models.enums import (
    GroupEventStatus,
    GroupHistoryEventType,
)
from app.models.group_event import GroupEvent
from app.models.user import User
from app.modules.groups.schemas import (
    GroupEventCreateRequest,
    GroupEventOut,
    GroupEventUpdateRequest,
)
from app.modules.groups.service_base import GroupsServiceBase


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
            is_paid=payload.is_paid,
            amount=payload.amount,
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
        self._validate_event_payment(next_is_paid, next_amount)

        if payload.title is not None:
            event.title = payload.title
        if "description" in payload.model_fields_set:
            event.description = payload.description
        if payload.date is not None:
            event.date = payload.date
        if payload.is_paid is not None:
            event.is_paid = payload.is_paid
        if "amount" in payload.model_fields_set:
            event.amount = payload.amount
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
