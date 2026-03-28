from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import AsyncSessionLocal, get_db_session
from app.core.security import (
    create_access_token,
    extract_telegram_user,
    validate_telegram_init_data,
)
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.modules.auth.schemas import (
    AuthResponse,
    CurrentUserResponse,
    TelegramWebAppUser,
    UserWorkspaceInfo,
    UserWorkspaceResponse,
)


def build_full_name(user: TelegramWebAppUser) -> str:
    """Build a stable display name from Telegram user fields."""
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    return full_name or user.username or f"telegram:{user.id}"


class AuthService:
    def __init__(
        self,
        session: Annotated[AsyncSession, Depends(get_db_session)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> None:
        self.session = session
        self.settings = settings

    async def authenticate_telegram(self, init_data: str) -> AuthResponse:
        """Validate Telegram initData, upsert the user, and issue a JWT."""
        try:
            validated_data = validate_telegram_init_data(
                init_data,
                self.settings.telegram_bot_token,
            )
            tg_user = TelegramWebAppUser.model_validate(extract_telegram_user(validated_data))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram initData",
            ) from exc

        user = await self.session.scalar(
            select(User).where(User.telegram_id == tg_user.id)
        )

        if user is None:
            user = User(
                telegram_id=tg_user.id,
                full_name=build_full_name(tg_user),
                username=tg_user.username,
                is_super_admin=tg_user.id == self.settings.super_admin_telegram_id,
            )
            self.session.add(user)
        else:
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User is inactive",
                )
            user.full_name = build_full_name(tg_user)
            user.username = tg_user.username
            if tg_user.id == self.settings.super_admin_telegram_id:
                user.is_super_admin = True

        await self.session.commit()
        await self.session.refresh(user)

        token = create_access_token(
            user_id=str(user.id),
            is_super_admin=user.is_super_admin,
            settings=self.settings,
        )

        return AuthResponse(
            access_token=token,
            user=CurrentUserResponse.model_validate(user),
        )

    async def get_user_workspaces(self, user: User) -> list[UserWorkspaceResponse]:
        """Return all active workspaces linked to the authenticated user."""
        result = await self.session.execute(
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(
                WorkspaceMember.user_id == user.id,
                WorkspaceMember.is_active.is_(True),
            )
            .order_by(Workspace.created_at.desc())
        )

        response: list[UserWorkspaceResponse] = []
        for workspace, role in result.all():
            response.append(
                UserWorkspaceResponse(
                    workspace=UserWorkspaceInfo(
                        id=workspace.id,
                        title=workspace.title,
                        slug=workspace.slug,
                        status=workspace.status,
                        plan=workspace.plan,
                    ),
                    role=role,
                )
            )
        return response


async def seed_super_admin() -> None:
    """Create or elevate the bootstrap super admin from environment settings."""
    settings = get_settings()
    if settings.super_admin_telegram_id is None:
        return

    async with AsyncSessionLocal() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == settings.super_admin_telegram_id)
        )
        if user is None:
            user = User(
                telegram_id=settings.super_admin_telegram_id,
                full_name=f"Super Admin {settings.super_admin_telegram_id}",
                username=None,
                is_super_admin=True,
            )
            session.add(user)
        else:
            user.is_super_admin = True

        await session.commit()
