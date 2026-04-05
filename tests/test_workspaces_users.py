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


class SeededWorkspaceUsers(TypedDict):
    workspace: Workspace
    admin: User
    assistant: User
    client: User
    inactive: User
    outsider: User
    super_admin: User


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        user_id=str(user.id),
        is_super_admin=user.is_super_admin,
        settings=get_settings(),
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_workspace_users(db_session: AsyncSession) -> SeededWorkspaceUsers:
    suffix = uuid4().hex[:8]
    telegram_seed = uuid4().int % 100_000_000
    workspace = Workspace(
        title=f"Users Workspace {suffix}",
        slug=f"users-workspace-{suffix}",
    )
    admin = User(
        telegram_id=7_100_000_000 + telegram_seed,
        full_name="Alexey Ivanov",
        username="alex_admin",
    )
    assistant = User(
        telegram_id=7_200_000_000 + telegram_seed,
        full_name="Maria Smirnova",
        username="maria_helper",
    )
    client = User(
        telegram_id=7_300_000_000 + telegram_seed,
        full_name="Client Person",
        username="client_user",
    )
    inactive = User(
        telegram_id=7_400_000_000 + telegram_seed,
        full_name="Inactive User",
        username="inactive_user",
    )
    outsider = User(
        telegram_id=7_500_000_000 + telegram_seed,
        full_name="Outsider User",
        username="outsider_user",
    )
    super_admin = User(
        telegram_id=7_600_000_000 + telegram_seed,
        full_name="Super Admin",
        username="super_admin_user",
        is_super_admin=True,
    )

    db_session.add_all([workspace, admin, assistant, client, inactive, outsider, super_admin])
    await db_session.flush()

    db_session.add_all(
        [
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=admin.id,
                role=WorkspaceRole.WORKSPACE_ADMIN,
                is_active=True,
                joined_at=datetime(2026, 1, 2, 10, 0, tzinfo=UTC),
            ),
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=assistant.id,
                role=WorkspaceRole.ASSISTANT,
                is_active=True,
                joined_at=datetime(2026, 1, 3, 10, 0, tzinfo=UTC),
            ),
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=client.id,
                role=WorkspaceRole.CLIENT,
                is_active=True,
                joined_at=datetime(2026, 1, 4, 10, 0, tzinfo=UTC),
            ),
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=inactive.id,
                role=WorkspaceRole.CLIENT,
                is_active=False,
                joined_at=datetime(2026, 1, 5, 10, 0, tzinfo=UTC),
            ),
        ]
    )
    await db_session.commit()

    return {
        "workspace": workspace,
        "admin": admin,
        "assistant": assistant,
        "client": client,
        "inactive": inactive,
        "outsider": outsider,
        "super_admin": super_admin,
    }


@pytest.mark.asyncio
async def test_list_workspace_users_returns_active_members_for_any_member_role(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_workspace_users(db_session)

    response = await client.get(
        f"/workspaces/{data['workspace'].id}/users",
        headers=_auth_headers(data["assistant"]),
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(data["client"].id),
            "full_name": "Client Person",
            "username": "client_user",
            "role": "client",
            "joined_at": "2026-01-04T10:00:00Z",
        },
        {
            "id": str(data["assistant"].id),
            "full_name": "Maria Smirnova",
            "username": "maria_helper",
            "role": "assistant",
            "joined_at": "2026-01-03T10:00:00Z",
        },
        {
            "id": str(data["admin"].id),
            "full_name": "Alexey Ivanov",
            "username": "alex_admin",
            "role": "workspace_admin",
            "joined_at": "2026-01-02T10:00:00Z",
        },
    ]


@pytest.mark.asyncio
async def test_list_workspace_users_filters_by_role(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_workspace_users(db_session)

    response = await client.get(
        f"/workspaces/{data['workspace'].id}/users",
        params={"role": "assistant"},
        headers=_auth_headers(data["admin"]),
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(data["assistant"].id),
            "full_name": "Maria Smirnova",
            "username": "maria_helper",
            "role": "assistant",
            "joined_at": "2026-01-03T10:00:00Z",
        }
    ]


@pytest.mark.asyncio
async def test_list_workspace_users_filters_by_search_case_insensitive(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_workspace_users(db_session)

    response = await client.get(
        f"/workspaces/{data['workspace'].id}/users",
        params={"search": "MARIA"},
        headers=_auth_headers(data["client"]),
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(data["assistant"].id),
            "full_name": "Maria Smirnova",
            "username": "maria_helper",
            "role": "assistant",
            "joined_at": "2026-01-03T10:00:00Z",
        }
    ]


@pytest.mark.asyncio
async def test_list_workspace_users_denies_non_member(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_workspace_users(db_session)

    response = await client.get(
        f"/workspaces/{data['workspace'].id}/users",
        headers=_auth_headers(data["outsider"]),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Workspace access denied"}


@pytest.mark.asyncio
async def test_list_workspace_users_allows_super_admin_without_membership(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_workspace_users(db_session)

    response = await client.get(
        f"/workspaces/{data['workspace'].id}/users",
        headers=_auth_headers(data["super_admin"]),
    )

    assert response.status_code == 200
    assert len(response.json()) == 3


@pytest.mark.asyncio
async def test_list_workspace_users_returns_empty_list_for_workspace_without_active_members(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:8]
    workspace = Workspace(
        title=f"Empty Workspace {suffix}",
        slug=f"empty-workspace-{suffix}",
    )
    super_admin = User(
        telegram_id=7_700_000_000 + (uuid4().int % 100_000_000),
        full_name="Super Admin",
        username="super_admin_empty",
        is_super_admin=True,
    )

    db_session.add_all([workspace, super_admin])
    await db_session.commit()

    response = await client.get(
        f"/workspaces/{workspace.id}/users",
        headers=_auth_headers(super_admin),
    )

    assert response.status_code == 200
    assert response.json() == []
