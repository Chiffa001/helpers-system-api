from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.core.exceptions import PlanLimitExceeded
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_invite import WorkspaceInvite
from app.models.workspace_member import WorkspaceMember
from app.modules.billing.schemas import PLAN_LIMITS
from app.modules.invites.schemas import (
    WorkspaceInviteAcceptResponse,
    WorkspaceInviteCreateRequest,
    WorkspaceInvitePublicResponse,
    WorkspaceInviteResponse,
    default_invite_expiration,
)


class InvitesService:
    def __init__(
        self,
        session: Annotated[AsyncSession, Depends(get_db_session)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> None:
        self.session = session
        self.settings = settings

    def _build_invite_url(self, workspace: Workspace, token: UUID) -> str:
        base_url = self.settings.telegram_mini_app_url
        if workspace.has_bot and workspace.mini_app_url:
            base_url = workspace.mini_app_url
        base_url = base_url.rstrip("/")
        return f"{base_url}?startapp=invite_{token}"

    def _ensure_invite_is_usable(self, invite: WorkspaceInvite) -> None:
        if invite.used_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invite token has already been used",
            )
        if invite.expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Invite token has expired",
            )

    async def create_invite(
        self,
        workspace: Workspace,
        created_by_user: User,
        payload: WorkspaceInviteCreateRequest,
    ) -> WorkspaceInviteResponse:
        await self._ensure_member_limit_available(workspace)

        invite = WorkspaceInvite(
            workspace_id=workspace.id,
            role=payload.role,
            created_by_user_id=created_by_user.id,
            expires_at=default_invite_expiration(),
        )
        self.session.add(invite)
        await self.session.commit()
        await self.session.refresh(invite)
        return WorkspaceInviteResponse(
            id=invite.id,
            token=invite.token,
            role=invite.role,
            expires_at=invite.expires_at,
            invite_url=self._build_invite_url(workspace, invite.token),
        )

    async def list_invites(self, workspace: Workspace) -> list[WorkspaceInviteResponse]:
        result = await self.session.scalars(
            select(WorkspaceInvite)
            .where(
                WorkspaceInvite.workspace_id == workspace.id,
                WorkspaceInvite.used_at.is_(None),
                WorkspaceInvite.expires_at > datetime.now(UTC),
            )
            .order_by(WorkspaceInvite.expires_at.asc())
        )
        invites = result.all()
        return [
            WorkspaceInviteResponse(
                id=invite.id,
                token=invite.token,
                role=invite.role,
                expires_at=invite.expires_at,
                invite_url=self._build_invite_url(workspace, invite.token),
            )
            for invite in invites
        ]

    async def revoke_invite(self, workspace_id: UUID, token: UUID) -> None:
        invite = await self.session.scalar(
            select(WorkspaceInvite).where(
                WorkspaceInvite.workspace_id == workspace_id,
                WorkspaceInvite.token == token,
            )
        )
        if invite is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite token not found",
            )
        await self.session.delete(invite)
        await self.session.commit()

    async def get_invite(self, token: UUID) -> WorkspaceInvitePublicResponse:
        invite = await self.session.scalar(
            select(WorkspaceInvite).where(WorkspaceInvite.token == token)
        )
        if invite is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite token not found",
            )
        self._ensure_invite_is_usable(invite)
        workspace_obj = await self.session.get(Workspace, invite.workspace_id)
        if workspace_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        return WorkspaceInvitePublicResponse(
            workspace_title=workspace_obj.title,
            role=invite.role,
            expires_at=invite.expires_at,
        )

    async def accept_invite(
        self,
        token: UUID,
        current_user: User,
    ) -> WorkspaceInviteAcceptResponse:
        invite = await self.session.scalar(
            select(WorkspaceInvite).where(WorkspaceInvite.token == token)
        )
        if invite is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite token not found",
            )
        self._ensure_invite_is_usable(invite)

        member = await self.session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == invite.workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        if member is not None and member.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a workspace member",
            )

        if member is None:
            member = WorkspaceMember(
                workspace_id=invite.workspace_id,
                user_id=current_user.id,
                role=invite.role,
            )
            self.session.add(member)
        else:
            member.role = invite.role
            member.is_active = True
            member.joined_at = datetime.now(UTC)

        invite.used_at = datetime.now(UTC)
        invite.used_by_user_id = current_user.id
        await self.session.commit()

        workspace_obj = await self.session.get(Workspace, invite.workspace_id)
        if workspace_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        return WorkspaceInviteAcceptResponse(
            workspace_id=invite.workspace_id,
            workspace_title=workspace_obj.title,
            role=invite.role,
        )

    async def _ensure_member_limit_available(self, workspace: Workspace) -> None:
        limit = PLAN_LIMITS[workspace.plan]["members"]
        if limit is None:
            return

        current_count = await self._count_active_members(workspace.id)
        if current_count >= limit:
            raise PlanLimitExceeded(
                current=current_count,
                limit=limit,
                plan=workspace.plan,
            )

    async def _count_active_members(self, workspace_id: UUID) -> int:
        result = await self.session.scalars(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.is_active.is_(True),
            )
        )
        return len(result.all())
