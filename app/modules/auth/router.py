from typing import Annotated

from fastapi import APIRouter, Depends

from app.middleware.auth import get_current_user
from app.models.user import User
from app.modules.auth.schemas import (
    AuthResponse,
    CurrentUserResponse,
    TelegramAuthRequest,
    UserWorkspaceResponse,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/telegram",
    response_model=AuthResponse,
    summary="Authorize via Telegram Mini App",
    description="Validates Telegram initData, creates or updates the user, and returns a JWT.",
)
async def authenticate_via_telegram(
    payload: TelegramAuthRequest,
    service: Annotated[AuthService, Depends(AuthService)],
) -> AuthResponse:
    """Exchange Telegram initData for an API access token."""
    return await service.authenticate_telegram(payload.init_data)


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get current user",
    description="Returns the authenticated user profile resolved from the bearer token.",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    """Return the current authenticated user."""
    return CurrentUserResponse.model_validate(current_user)


@router.get(
    "/me/workspaces",
    response_model=list[UserWorkspaceResponse],
    summary="List my workspaces",
    description="Returns workspaces where the current user is an active member, with their role.",
)
async def get_my_workspaces(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(AuthService)],
) -> list[UserWorkspaceResponse]:
    """Return the current user's accessible workspaces."""
    return await service.get_user_workspaces(current_user)
