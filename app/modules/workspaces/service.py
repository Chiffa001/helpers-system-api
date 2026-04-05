from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.enums import WorkspaceRole, WorkspaceStatus
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.modules.workspaces.schemas import (
    WorkspaceCreateRequest,
    WorkspaceDetailResponse,
    WorkspaceMemberCreateRequest,
    WorkspaceMemberResponse,
    WorkspaceMembersCount,
    WorkspaceMemberUpdateRequest,
    WorkspaceMemberUser,
    WorkspaceOut,
    WorkspaceUpdateRequest,
    WorkspaceUserResponse,
)


class WorkspacesService:
    def __init__(
        self,
        session: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> None:
        self.session = session

    async def list_workspaces(
        self,
        current_user: User,
        status_filter: WorkspaceStatus | None = None,
    ) -> list[WorkspaceOut]:
        """Return workspaces visible to the current user."""
        if current_user.is_super_admin:
            stmt = select(Workspace).order_by(Workspace.created_at.desc())
            if status_filter is not None:
                stmt = stmt.where(Workspace.status == status_filter)
        else:
            stmt = (
                select(Workspace)
                .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
                .where(
                    WorkspaceMember.user_id == current_user.id,
                    WorkspaceMember.is_active.is_(True),
                )
                .order_by(Workspace.created_at.desc())
            )
            if status_filter is not None:
                stmt = stmt.where(Workspace.status == status_filter)

        workspaces = (await self.session.scalars(stmt)).all()
        return [WorkspaceOut.model_validate(item) for item in workspaces]

    async def create_workspace(
        self,
        payload: WorkspaceCreateRequest,
        current_user: User,
    ) -> WorkspaceOut:
        """Create a workspace and optionally attach an admin member."""
        existing_workspace = await self.session.scalar(
            select(Workspace).where(Workspace.slug == payload.slug)
        )
        if existing_workspace is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Workspace slug is already taken",
            )

        workspace = Workspace(
            title=payload.title,
            slug=payload.slug,
            created_by_user_id=current_user.id,
        )
        self.session.add(workspace)
        await self.session.flush()

        if payload.admin_telegram_id is not None:
            admin_user = await self.session.scalar(
                select(User).where(User.telegram_id == payload.admin_telegram_id)
            )
            if admin_user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User with provided telegram_id not found",
                )
            self.session.add(
                WorkspaceMember(
                    workspace_id=workspace.id,
                    user_id=admin_user.id,
                    role=WorkspaceRole.WORKSPACE_ADMIN,
                )
            )

        await self.session.commit()
        await self.session.refresh(workspace)
        return WorkspaceOut.model_validate(workspace)

    async def get_workspace_detail(self, workspace: Workspace) -> WorkspaceDetailResponse:
        """Return workspace details with aggregated active member counts."""
        counts_result = await self.session.execute(
            select(WorkspaceMember.role, func.count(WorkspaceMember.id))
            .where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.is_active.is_(True),
            )
            .group_by(WorkspaceMember.role)
        )
        counts_map = {
            (role.value if hasattr(role, "value") else str(role)): count
            for role, count in counts_result.all()
        }

        members_count = WorkspaceMembersCount(
            workspace_admin=counts_map.get(WorkspaceRole.WORKSPACE_ADMIN.value, 0),
            assistant=counts_map.get(WorkspaceRole.ASSISTANT.value, 0),
            client=counts_map.get(WorkspaceRole.CLIENT.value, 0),
        )
        return WorkspaceDetailResponse(
            id=workspace.id,
            title=workspace.title,
            slug=workspace.slug,
            status=workspace.status,
            plan=workspace.plan,
            fee_rate=workspace.fee_rate,
            created_at=workspace.created_at,
            members_count=members_count,
        )

    async def update_workspace(
        self,
        workspace: Workspace,
        payload: WorkspaceUpdateRequest,
    ) -> WorkspaceOut:
        """Apply allowed workspace updates."""
        if payload.title is not None:
            workspace.title = payload.title
        if payload.status is not None:
            workspace.status = payload.status

        await self.session.commit()
        await self.session.refresh(workspace)
        return WorkspaceOut.model_validate(workspace)

    async def delete_workspace(self, workspace_id: UUID) -> None:
        """Delete a workspace."""
        workspace = await self.session.get(Workspace, workspace_id)
        if workspace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        await self.session.delete(workspace)
        await self.session.commit()

    async def list_members(self, workspace_id: UUID) -> list[WorkspaceMemberResponse]:
        """Return all members for a workspace."""
        result = await self.session.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.joined_at.asc())
        )

        members: list[WorkspaceMemberResponse] = []
        for member, user in result.all():
            members.append(
                WorkspaceMemberResponse(
                    id=member.id,
                    user=WorkspaceMemberUser(
                        id=user.id,
                        full_name=user.full_name,
                        username=user.username,
                    ),
                    role=member.role,
                    is_active=member.is_active,
                    joined_at=member.joined_at,
                )
            )
        return members

    async def list_users(
        self,
        workspace_id: UUID,
        role: WorkspaceRole | None = None,
        search: str | None = None,
    ) -> list[WorkspaceUserResponse]:
        """Return active workspace users with optional role and text filters."""
        query = (
            select(User, WorkspaceMember.role, WorkspaceMember.joined_at)
            .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.is_active.is_(True),
            )
            .order_by(WorkspaceMember.joined_at.desc())
        )

        if role is not None:
            query = query.where(WorkspaceMember.role == role)

        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    User.full_name.ilike(pattern),
                    User.username.ilike(pattern),
                )
            )

        result = await self.session.execute(query)
        return [
            WorkspaceUserResponse(
                id=user.id,
                full_name=user.full_name,
                username=user.username,
                role=member_role,
                joined_at=joined_at,
            )
            for user, member_role, joined_at in result.all()
        ]

    async def add_member(
        self,
        workspace_id: UUID,
        payload: WorkspaceMemberCreateRequest,
    ) -> WorkspaceMemberResponse:
        """Add or reactivate a workspace member by Telegram ID."""
        user = await self.session.scalar(
            select(User).where(User.telegram_id == payload.telegram_id)
        )
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User with provided telegram_id not found",
            )

        member = await self.session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user.id,
            )
        )
        if member is not None and member.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a workspace member",
            )

        if member is None:
            member = WorkspaceMember(
                workspace_id=workspace_id,
                user_id=user.id,
                role=payload.role,
            )
            self.session.add(member)
        else:
            member.role = payload.role
            member.is_active = True
            member.joined_at = datetime.now(UTC)

        await self.session.commit()
        await self.session.refresh(member)

        return WorkspaceMemberResponse(
            id=member.id,
            user=WorkspaceMemberUser(
                id=user.id,
                full_name=user.full_name,
                username=user.username,
            ),
            role=member.role,
            is_active=member.is_active,
            joined_at=member.joined_at,
        )

    async def update_member(
        self,
        workspace_id: UUID,
        user_id: UUID,
        payload: WorkspaceMemberUpdateRequest,
    ) -> WorkspaceMemberResponse:
        """Update workspace member role or active status."""
        result = await self.session.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        row = result.first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace member not found",
            )

        member, user = row
        if payload.role is not None:
            member.role = payload.role
        if payload.is_active is not None:
            member.is_active = payload.is_active

        await self.session.commit()
        await self.session.refresh(member)

        return WorkspaceMemberResponse(
            id=member.id,
            user=WorkspaceMemberUser(
                id=user.id,
                full_name=user.full_name,
                username=user.username,
            ),
            role=member.role,
            is_active=member.is_active,
            joined_at=member.joined_at,
        )

    async def deactivate_member(
        self,
        workspace_id: UUID,
        user_id: UUID,
        current_user: User,
    ) -> None:
        """Soft-delete a workspace membership."""
        if user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot remove yourself from the workspace",
            )

        member = await self.session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace member not found",
            )

        member.is_active = False
        await self.session.commit()
