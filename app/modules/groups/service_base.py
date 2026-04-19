from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.enums import (
    GroupHistoryEventType,
    GroupMemberRole,
    InvoiceStatus,
    WorkspaceRole,
)
from app.models.group import Group
from app.models.group_event import GroupEvent
from app.models.group_favorite import GroupFavorite
from app.models.group_history_entry import GroupHistoryEntry
from app.models.group_member import GroupMember
from app.models.user import User
from app.models.workspace_member import WorkspaceMember

ActorRole = Literal["super_admin"] | WorkspaceRole


@dataclass(slots=True)
class GroupAccessContext:
    group: Group
    actor_role: ActorRole
    group_member_role: GroupMemberRole | None


class GroupsServiceBase:
    def __init__(
        self,
        session: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> None:
        self.session = session

    async def _get_workspace_group(self, workspace_id: UUID, group_id: UUID) -> Group:
        group = await self.session.scalar(
            select(Group).where(
                Group.id == group_id,
                Group.workspace_id == workspace_id,
            )
        )
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found",
            )
        return group

    async def _get_group(self, group_id: UUID) -> Group:
        group = await self.session.get(Group, group_id)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found",
            )
        return group

    async def _ensure_workspace_member(
        self,
        workspace_id: UUID,
        user_id: UUID,
        group_role: GroupMemberRole,
    ) -> None:
        workspace_member = await self.session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.is_active.is_(True),
            )
        )
        if workspace_member is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must be an active workspace member before joining the group",
            )

        expected_role = (
            WorkspaceRole.ASSISTANT
            if group_role == GroupMemberRole.ASSISTANT
            else WorkspaceRole.CLIENT
        )
        if workspace_member.role != expected_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Group member role must match workspace role",
            )

    async def _require_group_read_access(
        self,
        workspace_id: UUID,
        group_id: UUID,
        current_user: User,
    ) -> GroupAccessContext:
        group = await self._get_workspace_group(workspace_id, group_id)
        if current_user.is_super_admin:
            return GroupAccessContext(
                group=group,
                actor_role="super_admin",
                group_member_role=None,
            )

        workspace_member = await self.session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user.id,
                WorkspaceMember.is_active.is_(True),
            )
        )
        if workspace_member is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workspace access denied",
            )

        if workspace_member.role == WorkspaceRole.WORKSPACE_ADMIN:
            return GroupAccessContext(
                group=group,
                actor_role=workspace_member.role,
                group_member_role=None,
            )

        group_member = await self.session.scalar(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == current_user.id,
                GroupMember.is_active.is_(True),
            )
        )
        if group_member is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Group access denied",
            )

        return GroupAccessContext(
            group=group,
            actor_role=workspace_member.role,
            group_member_role=group_member.role,
        )

    async def _require_group_read_access_by_group_id(
        self,
        group_id: UUID,
        current_user: User,
    ) -> GroupAccessContext:
        group = await self._get_group(group_id)
        return await self._require_group_read_access(group.workspace_id, group_id, current_user)

    async def _require_group_write_access(
        self,
        workspace_id: UUID,
        group_id: UUID,
        current_user: User,
    ) -> GroupAccessContext:
        ctx = await self._require_group_read_access(workspace_id, group_id, current_user)
        if ctx.actor_role in {
            "super_admin",
            WorkspaceRole.WORKSPACE_ADMIN,
            WorkspaceRole.ASSISTANT,
        }:
            return ctx
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient group permissions",
        )

    async def _ensure_group_assistant(self, group_id: UUID, user_id: UUID) -> None:
        member = await self.session.scalar(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
                GroupMember.role == GroupMemberRole.ASSISTANT,
                GroupMember.is_active.is_(True),
            )
        )
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned user must be an active assistant in the group",
            )

    async def _ensure_group_client(self, group_id: UUID, user_id: UUID) -> None:
        member = await self.session.scalar(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
                GroupMember.role == GroupMemberRole.CLIENT,
                GroupMember.is_active.is_(True),
            )
        )
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invoice client must be an active client in the group",
            )

    async def _ensure_group_event(self, group_id: UUID, group_event_id: UUID) -> None:
        event = await self.session.scalar(
            select(GroupEvent).where(
                GroupEvent.id == group_event_id,
                GroupEvent.group_id == group_id,
            )
        )
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invoice event must belong to the group",
            )

    async def _record_history(
        self,
        group_id: UUID,
        actor_user_id: UUID | None,
        event_type: GroupHistoryEventType,
        payload: dict[str, object],
    ) -> None:
        self.session.add(
            GroupHistoryEntry(
                group_id=group_id,
                actor_user_id=actor_user_id,
                event_type=event_type,
                payload=payload,
            )
        )

    def _validate_event_payment(
        self,
        is_paid: bool,
        amount: Decimal | None,
        currency: str | None,
        due_date: datetime | None,
    ) -> None:
        if is_paid and amount is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="amount is required for paid events",
            )
        if is_paid and currency is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="currency is required for paid events",
            )
        if not is_paid and amount is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="amount must be null for free events",
            )
        if not is_paid and currency is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="currency must be null for free events",
            )
        if not is_paid and due_date is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="due_date must be null for free events",
            )

    def _invoice_history_event(
        self,
        status_value: InvoiceStatus,
    ) -> GroupHistoryEventType | None:
        mapping = {
            InvoiceStatus.PAID: GroupHistoryEventType.INVOICE_PAID,
            InvoiceStatus.CANCELLED: GroupHistoryEventType.INVOICE_CANCELLED,
            InvoiceStatus.EXPIRED: GroupHistoryEventType.INVOICE_EXPIRED,
        }
        return mapping.get(status_value)

    def _dt(self, value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    def _decimal(self, value: Decimal) -> str:
        return format(value, "f")

    async def _favorite_group_ids(
        self,
        user_id: UUID,
        group_ids: list[UUID],
    ) -> set[UUID]:
        if not group_ids:
            return set()
        result = await self.session.scalars(
            select(GroupFavorite.group_id).where(
                GroupFavorite.user_id == user_id,
                GroupFavorite.group_id.in_(group_ids),
            )
        )
        return set(result.all())
