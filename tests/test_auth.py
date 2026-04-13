from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import encrypt_bot_token
from app.models.workspace import Workspace

TG_USER: dict[str, Any] = {
    "id": 9000000001,
    "first_name": "Test",
    "last_name": "User",
    "username": "testuser",
}

AUTH_BODY: dict[str, Any] = {
    "user": TG_USER,
    "auth_date": 1700000000,
    "hash": "fakehash",
}

TG_HASH_HEADER = {"x-tg-hash": "mocked"}


@pytest.mark.asyncio
async def test_auth_missing_header(client: AsyncClient) -> None:
    response = await client.post("/auth/telegram", json=AUTH_BODY)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_invalid_init_data(client: AsyncClient) -> None:
    response = await client.post("/auth/telegram", json=AUTH_BODY, headers={"x-tg-hash": "invalid"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid Telegram auth data"}


@pytest.mark.asyncio
async def test_auth_missing_bearer(client: AsyncClient) -> None:
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_invalid_token(client: AsyncClient) -> None:
    response = await client.get("/auth/me", headers={"Authorization": "Bearer badtoken"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_telegram_success(client: AsyncClient) -> None:
    with patch(
        "app.modules.auth.service.validate_telegram_init_data",
        return_value={},
    ):
        response = await client.post("/auth/telegram", json=AUTH_BODY, headers=TG_HASH_HEADER)

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data
    assert data["user"]["full_name"] == "Test User"
    assert data["user"]["username"] == "testuser"
    assert data["user"]["is_super_admin"] is False


@pytest.mark.asyncio
async def test_auth_me(client: AsyncClient) -> None:
    with patch(
        "app.modules.auth.service.validate_telegram_init_data",
        return_value={},
    ):
        auth = await client.post("/auth/telegram", json=AUTH_BODY, headers=TG_HASH_HEADER)

    token = auth.json()["access_token"]
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"


@pytest.mark.asyncio
async def test_auth_me_workspaces_empty(client: AsyncClient) -> None:
    with patch(
        "app.modules.auth.service.validate_telegram_init_data",
        return_value={},
    ):
        auth = await client.post("/auth/telegram", json=AUTH_BODY, headers=TG_HASH_HEADER)

    token = auth.json()["access_token"]
    response = await client.get("/auth/me/workspaces", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_auth_telegram_uses_workspace_bot_token_when_workspace_slug_is_provided(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:8]
    workspace = Workspace(
        title="Clinic Workspace",
        slug=f"clinic-{suffix}",
        bot_token=encrypt_bot_token(
            "workspace-bot-token",
            get_settings().bot_token_encryption_key,
        ),
    )
    db_session.add(workspace)
    await db_session.commit()

    body = {**AUTH_BODY, "workspace_slug": workspace.slug}

    with patch(
        "app.modules.auth.service.validate_telegram_init_data",
        return_value={},
    ) as validate_mock:
        response = await client.post("/auth/telegram", json=body, headers=TG_HASH_HEADER)

    assert response.status_code == 200
    validate_mock.assert_called_once_with("mocked", "workspace-bot-token")
    await db_session.close()


@pytest.mark.asyncio
async def test_auth_telegram_returns_404_for_unknown_workspace_slug(
    client: AsyncClient,
) -> None:
    body = {**AUTH_BODY, "workspace_slug": "missing-workspace"}

    response = await client.post("/auth/telegram", json=body, headers=TG_HASH_HEADER)

    assert response.status_code == 404
    assert response.json() == {"detail": "Workspace not found"}
