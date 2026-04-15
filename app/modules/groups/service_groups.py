from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from app.models.enums import GroupHistoryEventType, GroupStatus, WorkspaceRole
from app.models.group import Group
from app.models.group_history_entry import GroupHistoryEntry
from app.models.group_member import GroupMember
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.modules.groups.schemas import (
    GroupCreateRequest,
    GroupHistoryEntryOut,
    GroupMemberCreateRequest,
    GroupMemberResponse,
    GroupMemberUser,
    GroupOut,
    GroupUpdateRequest,
)
from app.modules.groups.service_base import GroupsServiceBase


class GroupsCoreMixin(GroupsServiceBase):
    async def list_groups(
        self,
        workspace: Workspace,
        current_user: User,
        status_filter: GroupStatus | None = None,
    ) -> list[GroupOut]:
        stmt = select(Group).where(Group.workspace_id == workspace.id)
        if status_filter is not None:
            stmt = stmt.where(Group.status == status_filter)

        if not current_user.is_super_admin:
            workspace_member = await self.session.scalar(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace.id,
                    WorkspaceMember.user_id == current_user.id,
                    WorkspaceMember.is_active.is_(True),
                )
            )
            if workspace_member is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Workspace access denied",
                )

            if workspace_member.role != WorkspaceRole.WORKSPACE_ADMIN:
                stmt = stmt.join(GroupMember, GroupMember.group_id == Group.id).where(
                    GroupMember.user_id == current_user.id,
                    GroupMember.is_active.is_(True),
                )

        stmt = stmt.order_by(Group.created_at.desc(), Group.id.desc())
        groups = (await self.session.scalars(stmt)).all()
        favorite_group_ids = await self._favorite_group_ids(
            current_user.id,
            [group.id for group in groups],
        )
        ordered_groups = sorted(
            groups,
            key=lambda group: (
                group.id not in favorite_group_ids,
                -(group.created_at.timestamp() if group.created_at else 0),
                group.title.lower(),
            ),
        )
        return [
            GroupOut(
                id=group.id,
                workspace_id=group.workspace_id,
                title=group.title,
                description=group.description,
                status=group.status,
                is_favorite=group.id in favorite_group_ids,
                created_by_user_id=group.created_by_user_id,
                created_at=group.created_at,
            )
            for group in ordered_groups
        ]

    async def create_group(
        self,
        workspace: Workspace,
        current_user: User,
        payload: GroupCreateRequest,
    ) -> GroupOut:
        group = Group(
            workspace_id=workspace.id,
            title=payload.title,
            description=payload.description,
            created_by_user_id=current_user.id,
        )
        self.session.add(group)
        await self.session.commit()
        await self.session.refresh(group)
        return GroupOut.model_validate(group)

    async def update_group(
        self,
        workspace_id: UUID,
        group_id: UUID,
        payload: GroupUpdateRequest,
    ) -> GroupOut:
        group = await self._get_workspace_group(workspace_id, group_id)
        if payload.title is not None:
            group.title = payload.title
        if "description" in payload.model_fields_set:
            group.description = payload.description
        if payload.status is not None:
            group.status = payload.status

        await self.session.commit()
        await self.session.refresh(group)
        return GroupOut.model_validate(group)

    async def list_members(
        self,
        workspace_id: UUID,
        group_id: UUID,
    ) -> list[GroupMemberResponse]:
        await self._get_workspace_group(workspace_id, group_id)
        result = await self.session.execute(
            select(GroupMember, User)
            .join(User, User.id == GroupMember.user_id)
            .where(GroupMember.group_id == group_id)
            .order_by(GroupMember.joined_at.asc())
        )
        return [
            GroupMemberResponse(
                id=member.id,
                user=GroupMemberUser(
                    id=user.id,
                    full_name=user.full_name,
                    username=user.username,
                ),
                role=member.role,
                is_active=member.is_active,
                joined_at=member.joined_at,
            )
            for member, user in result.all()
        ]

    async def add_member(
        self,
        workspace_id: UUID,
        group_id: UUID,
        payload: GroupMemberCreateRequest,
        actor: User | None = None,
    ) -> GroupMemberResponse:
        await self._get_workspace_group(workspace_id, group_id)
        await self._ensure_workspace_member(workspace_id, payload.user_id, payload.role)

        user = await self.session.get(User, payload.user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        member = await self.session.scalar(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == payload.user_id,
            )
        )
        if member is not None and member.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a group member",
            )

        if member is None:
            member = GroupMember(
                group_id=group_id,
                user_id=payload.user_id,
                role=payload.role,
            )
            self.session.add(member)
        else:
            member.role = payload.role
            member.is_active = True
            member.joined_at = datetime.now(UTC)

        await self._record_history(
            group_id=group_id,
            actor_user_id=actor.id if actor else None,
            event_type=GroupHistoryEventType.MEMBER_ADDED,
            payload={
                "user_id": str(payload.user_id),
                "role": payload.role.value,
            },
        )
        await self.session.commit()
        await self.session.refresh(member)
        return GroupMemberResponse(
            id=member.id,
            user=GroupMemberUser(
                id=user.id,
                full_name=user.full_name,
                username=user.username,
            ),
            role=member.role,
            is_active=member.is_active,
            joined_at=member.joined_at,
        )

    async def remove_member(
        self,
        workspace_id: UUID,
        group_id: UUID,
        user_id: UUID,
        actor: User | None = None,
    ) -> None:
        await self._get_workspace_group(workspace_id, group_id)
        member = await self.session.scalar(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
            )
        )
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group member not found",
            )

        member.is_active = False
        await self._record_history(
            group_id=group_id,
            actor_user_id=actor.id if actor else None,
            event_type=GroupHistoryEventType.MEMBER_REMOVED,
            payload={
                "user_id": str(user_id),
                "role": member.role.value,
            },
        )
        await self.session.commit()

    async def list_history(
        self,
        workspace_id: UUID,
        group_id: UUID,
        current_user: User,
    ) -> list[GroupHistoryEntryOut]:
        await self._require_group_read_access(workspace_id, group_id, current_user)
        result = await self.session.scalars(
            select(GroupHistoryEntry)
            .where(GroupHistoryEntry.group_id == group_id)
            .order_by(GroupHistoryEntry.created_at.desc(), GroupHistoryEntry.id.desc())
        )
        return [GroupHistoryEntryOut.model_validate(item) for item in result.all()]
