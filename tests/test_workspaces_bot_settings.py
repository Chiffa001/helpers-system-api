from datetime import UTC, datetime
from typing import TypedDict
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.enums import WorkspaceRole
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember


class SeededWorkspaceAdminData(TypedDict):
    workspace: Workspace
    admin: User


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        user_id=str(user.id),
        is_super_admin=user.is_super_admin,
        settings=get_settings(),
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_workspace_admin(db_session: AsyncSession) -> SeededWorkspaceAdminData:
    suffix = uuid4().hex[:8]
    telegram_seed = uuid4().int % 100_000_000
    workspace = Workspace(
        title=f"Bot Settings Workspace {suffix}",
        slug=f"bot-settings-{suffix}",
    )
    admin = User(
        telegram_id=7_840_000_000 + telegram_seed,
        full_name="Workspace Admin",
        username="workspace_admin",
    )

    db_session.add_all([workspace, admin])
    await db_session.flush()
    db_session.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=admin.id,
            role=WorkspaceRole.WORKSPACE_ADMIN,
            is_active=True,
            joined_at=datetime(2026, 1, 10, 10, 0, tzinfo=UTC),
        )
    )
    await db_session.commit()

    return {
        "workspace": workspace,
        "admin": admin,
    }


@pytest.mark.asyncio
async def test_workspace_admin_can_update_bot_settings(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_workspace_admin(db_session)

    response = await client.patch(
        f"/workspaces/{data['workspace'].id}",
        json={
            "bot_token": "workspace-secret-token",
            "bot_username": "ClinicBot",
            "mini_app_url": "https://t.me/ClinicBot/App",
        },
        headers=_auth_headers(data["admin"]),
    )

    assert response.status_code == 200
    assert response.json()["has_bot"] is True
    assert response.json()["bot_username"] == "ClinicBot"
    assert response.json()["mini_app_url"] == "https://t.me/ClinicBot/App"
    assert "bot_token" not in response.json()

    get_response = await client.get(
        f"/workspaces/{data['workspace'].id}",
        headers=_auth_headers(data["admin"]),
    )

    assert get_response.status_code == 200
    assert get_response.json()["has_bot"] is True
    assert get_response.json()["bot_username"] == "ClinicBot"
    assert get_response.json()["mini_app_url"] == "https://t.me/ClinicBot/App"
    assert "bot_token" not in get_response.json()
    await db_session.close()
