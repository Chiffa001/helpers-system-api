from datetime import UTC, datetime
from typing import TypedDict
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.enums import GroupMemberRole, GroupStatus, WorkspaceRole
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember


class SeededGroupsData(TypedDict):
    workspace: Workspace
    admin: User
    assistant: User
    client: User
    other_assistant: User
    outsider: User
    super_admin: User
    assistant_group: Group
    other_group: Group


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        user_id=str(user.id),
        is_super_admin=user.is_super_admin,
        settings=get_settings(),
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_groups_data(db_session: AsyncSession) -> SeededGroupsData:
    suffix = uuid4().hex[:8]
    telegram_seed = uuid4().int % 100_000_000

    workspace = Workspace(
        title=f"Groups Workspace {suffix}",
        slug=f"groups-workspace-{suffix}",
    )
    admin = User(
        telegram_id=7_900_000_000 + telegram_seed,
        full_name="Workspace Admin",
        username="workspace_admin",
    )
    assistant = User(
        telegram_id=7_901_000_000 + telegram_seed,
        full_name="Assigned Assistant",
        username="assigned_assistant",
    )
    client = User(
        telegram_id=7_902_000_000 + telegram_seed,
        full_name="Assigned Client",
        username="assigned_client",
    )
    other_assistant = User(
        telegram_id=7_903_000_000 + telegram_seed,
        full_name="Other Assistant",
        username="other_assistant",
    )
    outsider = User(
        telegram_id=7_904_000_000 + telegram_seed,
        full_name="Outsider",
        username="outsider",
    )
    super_admin = User(
        telegram_id=7_905_000_000 + telegram_seed,
        full_name="Super Admin",
        username="super_admin",
        is_super_admin=True,
    )

    db_session.add_all(
        [workspace, admin, assistant, client, other_assistant, outsider, super_admin]
    )
    await db_session.flush()

    db_session.add_all(
        [
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=admin.id,
                role=WorkspaceRole.WORKSPACE_ADMIN,
                joined_at=datetime(2026, 1, 10, 10, 0, tzinfo=UTC),
            ),
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=assistant.id,
                role=WorkspaceRole.ASSISTANT,
                joined_at=datetime(2026, 1, 10, 10, 5, tzinfo=UTC),
            ),
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=client.id,
                role=WorkspaceRole.CLIENT,
                joined_at=datetime(2026, 1, 10, 10, 10, tzinfo=UTC),
            ),
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=other_assistant.id,
                role=WorkspaceRole.ASSISTANT,
                joined_at=datetime(2026, 1, 10, 10, 15, tzinfo=UTC),
            ),
        ]
    )
    await db_session.flush()

    assistant_group = Group(
        workspace_id=workspace.id,
        title="Client Ivanov",
        description="Assigned group",
        created_by_user_id=admin.id,
    )
    other_group = Group(
        workspace_id=workspace.id,
        title="Family Petrov",
        description="Hidden from assistant",
        status=GroupStatus.ARCHIVED,
        created_by_user_id=admin.id,
    )
    db_session.add_all([assistant_group, other_group])
    await db_session.flush()

    db_session.add_all(
        [
            GroupMember(
                group_id=assistant_group.id,
                user_id=assistant.id,
                role=GroupMemberRole.ASSISTANT,
                joined_at=datetime(2026, 1, 10, 11, 0, tzinfo=UTC),
            ),
            GroupMember(
                group_id=assistant_group.id,
                user_id=client.id,
                role=GroupMemberRole.CLIENT,
                joined_at=datetime(2026, 1, 10, 11, 5, tzinfo=UTC),
            ),
        ]
    )
    await db_session.commit()

    return {
        "workspace": workspace,
        "admin": admin,
        "assistant": assistant,
        "client": client,
        "other_assistant": other_assistant,
        "outsider": outsider,
        "super_admin": super_admin,
        "assistant_group": assistant_group,
        "other_group": other_group,
    }


@pytest.mark.asyncio
async def test_list_groups_for_workspace_admin_returns_all_workspace_groups(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_groups_data(db_session)

    response = await client.get(
        f"/workspaces/{data['workspace'].id}/groups",
        headers=_auth_headers(data["admin"]),
    )

    assert response.status_code == 200
    assert sorted(item["id"] for item in response.json()) == sorted(
        [
            str(data["other_group"].id),
            str(data["assistant_group"].id),
        ]
    )
    assert {item["is_favorite"] for item in response.json()} == {False}


@pytest.mark.asyncio
async def test_list_groups_for_assistant_returns_only_joined_groups(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_groups_data(db_session)

    response = await client.get(
        f"/workspaces/{data['workspace'].id}/groups",
        headers=_auth_headers(data["assistant"]),
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(data["assistant_group"].id),
            "workspace_id": str(data["workspace"].id),
            "title": "Client Ivanov",
            "description": "Assigned group",
            "status": "active",
            "is_favorite": False,
            "created_by_user_id": str(data["admin"].id),
            "created_at": response.json()[0]["created_at"],
        }
    ]


@pytest.mark.asyncio
async def test_workspace_admin_can_create_archive_and_manage_group_members(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_groups_data(db_session)

    create_response = await client.post(
        f"/workspaces/{data['workspace'].id}/groups",
        json={"title": "Client Sidorov", "description": "New group"},
        headers=_auth_headers(data["admin"]),
    )

    assert create_response.status_code == 201
    created_group_id = create_response.json()["id"]

    add_member_response = await client.post(
        f"/workspaces/{data['workspace'].id}/groups/{created_group_id}/members",
        json={
            "user_id": str(data["other_assistant"].id),
            "role": "assistant",
        },
        headers=_auth_headers(data["admin"]),
    )

    assert add_member_response.status_code == 201
    assert add_member_response.json()["user"]["id"] == str(data["other_assistant"].id)

    archive_response = await client.patch(
        f"/workspaces/{data['workspace'].id}/groups/{created_group_id}",
        json={"status": "archived"},
        headers=_auth_headers(data["admin"]),
    )

    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"

    remove_response = await client.delete(
        f"/workspaces/{data['workspace'].id}/groups/"
        f"{created_group_id}/members/{data['other_assistant'].id}",
        headers=_auth_headers(data["admin"]),
    )

    assert remove_response.status_code == 204


@pytest.mark.asyncio
async def test_add_group_member_requires_matching_workspace_role(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_groups_data(db_session)

    response = await client.post(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/members",
        json={
            "user_id": str(data["client"].id),
            "role": "assistant",
        },
        headers=_auth_headers(data["admin"]),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Group member role must match workspace role"}


@pytest.mark.asyncio
async def test_non_admin_cannot_create_group(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_groups_data(db_session)

    response = await client.post(
        f"/workspaces/{data['workspace'].id}/groups",
        json={"title": "Forbidden"},
        headers=_auth_headers(data["assistant"]),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient workspace permissions"}


@pytest.mark.asyncio
async def test_group_favorite_is_idempotent_and_moves_group_to_top(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_groups_data(db_session)

    favorite_response = await client.post(
        f"/groups/{data['assistant_group'].id}/favorite",
        headers=_auth_headers(data["assistant"]),
    )
    assert favorite_response.status_code == 200
    assert favorite_response.json() == {"is_favorite": True}

    second_favorite_response = await client.post(
        f"/groups/{data['assistant_group'].id}/favorite",
        headers=_auth_headers(data["assistant"]),
    )
    assert second_favorite_response.status_code == 200
    assert second_favorite_response.json() == {"is_favorite": True}

    list_response = await client.get(
        f"/workspaces/{data['workspace'].id}/groups",
        headers=_auth_headers(data["assistant"]),
    )
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == str(data["assistant_group"].id)
    assert list_response.json()[0]["is_favorite"] is True

    unfavorite_response = await client.delete(
        f"/groups/{data['assistant_group'].id}/favorite",
        headers=_auth_headers(data["assistant"]),
    )
    assert unfavorite_response.status_code == 200
    assert unfavorite_response.json() == {"is_favorite": False}

    second_unfavorite_response = await client.delete(
        f"/groups/{data['assistant_group'].id}/favorite",
        headers=_auth_headers(data["assistant"]),
    )
    assert second_unfavorite_response.status_code == 200
    assert second_unfavorite_response.json() == {"is_favorite": False}


@pytest.mark.asyncio
async def test_client_cannot_favorite_inaccessible_group(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_groups_data(db_session)

    response = await client.post(
        f"/groups/{data['other_group'].id}/favorite",
        headers=_auth_headers(data["client"]),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Group access denied"}
