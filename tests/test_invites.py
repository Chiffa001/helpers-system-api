from datetime import UTC, datetime, timedelta
from typing import TypedDict
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.enums import GroupMemberRole, WorkspacePlan, WorkspaceRole
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_invite import WorkspaceInvite
from app.models.workspace_member import WorkspaceMember


class SeededInviteData(TypedDict):
    workspace: Workspace
    group: Group
    admin: User
    assistant: User
    client: User
    super_admin: User
    invitee: User
    outsider: User


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        user_id=str(user.id),
        is_super_admin=user.is_super_admin,
        settings=get_settings(),
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_invite_data(db_session: AsyncSession) -> SeededInviteData:
    suffix = uuid4().hex[:8]
    telegram_seed = uuid4().int % 100_000_000

    workspace = Workspace(
        title=f"Invite Workspace {suffix}",
        slug=f"invite-workspace-{suffix}",
        bot_username="ClinicBot",
        bot_mini_app_name="App",
    )
    admin = User(
        telegram_id=7_810_000_000 + telegram_seed,
        full_name="Workspace Admin",
        username="workspace_admin",
    )
    assistant = User(
        telegram_id=7_811_000_000 + telegram_seed,
        full_name="Workspace Assistant",
        username="workspace_assistant",
    )
    client = User(
        telegram_id=7_812_000_000 + telegram_seed,
        full_name="Workspace Client",
        username="workspace_client",
    )
    super_admin = User(
        telegram_id=7_813_000_000 + telegram_seed,
        full_name="Platform Super Admin",
        username="platform_super_admin",
        is_super_admin=True,
    )
    invitee = User(
        telegram_id=7_820_000_000 + telegram_seed,
        full_name="Accepted Assistant",
        username="accepted_assistant",
    )
    outsider = User(
        telegram_id=7_830_000_000 + telegram_seed,
        full_name="Outside User",
        username="outside_user",
    )

    db_session.add_all([workspace, admin, assistant, client, super_admin, invitee, outsider])
    await db_session.flush()

    group = Group(
        workspace_id=workspace.id,
        title=f"Invite Group {suffix}",
        created_by_user_id=admin.id,
    )
    db_session.add(group)
    await db_session.flush()

    db_session.add_all(
        [
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=admin.id,
                role=WorkspaceRole.WORKSPACE_ADMIN,
                is_active=True,
                joined_at=datetime(2026, 1, 10, 10, 0, tzinfo=UTC),
            ),
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=assistant.id,
                role=WorkspaceRole.ASSISTANT,
                is_active=True,
                joined_at=datetime(2026, 1, 10, 10, 5, tzinfo=UTC),
            ),
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=client.id,
                role=WorkspaceRole.CLIENT,
                is_active=True,
                joined_at=datetime(2026, 1, 10, 10, 10, tzinfo=UTC),
            ),
        ]
    )
    await db_session.commit()

    return {
        "workspace": workspace,
        "group": group,
        "admin": admin,
        "assistant": assistant,
        "client": client,
        "super_admin": super_admin,
        "invitee": invitee,
        "outsider": outsider,
    }


@pytest.mark.asyncio
async def test_create_and_list_workspace_invites(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)

    create_response = await client.post(
        f"/workspaces/{data['workspace'].id}/invites",
        json={"role": "assistant"},
        headers=_auth_headers(data["admin"]),
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["role"] == "assistant"
    assert created["group_id"] is None
    assert (
        created["invite_url"]
        == f"{get_settings().telegram_mini_app_url}?startapp=invite_{created['token']}"
    )

    list_response = await client.get(
        f"/workspaces/{data['workspace'].id}/invites",
        headers=_auth_headers(data["admin"]),
    )

    assert list_response.status_code == 200
    assert list_response.json() == [created]
    await db_session.close()


@pytest.mark.asyncio
async def test_create_invite_uses_base_bot_when_workspace_bot_is_not_connected(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)

    response = await client.post(
        f"/workspaces/{data['workspace'].id}/invites",
        json={"role": "assistant"},
        headers=_auth_headers(data["admin"]),
    )

    assert response.status_code == 201
    assert (
        response.json()["invite_url"]
        == f"{get_settings().telegram_mini_app_url}?startapp=invite_{response.json()['token']}"
    )
    await db_session.close()


@pytest.mark.asyncio
async def test_workspace_admin_can_create_invites_for_all_supported_roles(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)

    for role in ("workspace_admin", "assistant"):
        response = await client.post(
            f"/workspaces/{data['workspace'].id}/invites",
            json={"role": role},
            headers=_auth_headers(data["admin"]),
        )

        assert response.status_code == 201
        assert response.json()["role"] == role
        assert response.json()["group_id"] is None

    await db_session.close()


@pytest.mark.asyncio
async def test_create_invite_uses_workspace_bot_when_bot_is_connected(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)
    data["workspace"].bot_token = "encrypted-bot-token"
    await db_session.commit()

    response = await client.post(
        f"/workspaces/{data['workspace'].id}/invites",
        json={"role": "assistant"},
        headers=_auth_headers(data["admin"]),
    )

    assert response.status_code == 201
    assert response.json()["group_id"] is None
    assert (
        response.json()["invite_url"]
        == f"https://t.me/ClinicBot/App?startapp=invite_{response.json()['token']}"
    )
    await db_session.close()


@pytest.mark.asyncio
async def test_super_admin_can_create_workspace_admin_invite_without_membership(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)

    response = await client.post(
        f"/workspaces/{data['workspace'].id}/invites",
        json={"role": "workspace_admin"},
        headers=_auth_headers(data["super_admin"]),
    )

    assert response.status_code == 201
    assert response.json()["role"] == "workspace_admin"
    await db_session.close()


@pytest.mark.asyncio
async def test_assistant_cannot_create_invite(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)

    response = await client.post(
        f"/workspaces/{data['workspace'].id}/invites",
        json={"role": "assistant"},
        headers=_auth_headers(data["assistant"]),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient workspace permissions"}
    await db_session.close()


@pytest.mark.asyncio
async def test_client_cannot_create_invite(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)

    response = await client.post(
        f"/workspaces/{data['workspace'].id}/invites",
        json={"role": "assistant"},
        headers=_auth_headers(data["client"]),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient workspace permissions"}
    await db_session.close()


@pytest.mark.asyncio
async def test_create_invite_returns_plan_limit_exceeded_when_member_slots_are_full(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)
    data["workspace"].plan = WorkspacePlan.FREE

    extra_users: list[User] = []
    extra_members: list[WorkspaceMember] = []
    for idx in range(2):
        user = User(
            telegram_id=7_840_000_000 + idx + (uuid4().int % 100_000),
            full_name=f"Extra Member {idx}",
            username=f"extra_member_{idx}",
        )
        extra_users.append(user)
    db_session.add_all(extra_users)
    await db_session.flush()

    for idx, user in enumerate(extra_users):
        extra_members.append(
            WorkspaceMember(
                workspace_id=data["workspace"].id,
                user_id=user.id,
                role=WorkspaceRole.CLIENT,
                is_active=True,
                joined_at=datetime(2026, 1, 10, 11, idx, tzinfo=UTC),
            )
        )
    db_session.add_all(extra_members)
    await db_session.commit()

    response = await client.post(
        f"/workspaces/{data['workspace'].id}/invites",
        json={"role": "client", "group_id": str(data["group"].id)},
        headers=_auth_headers(data["admin"]),
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": "plan_limit_exceeded",
        "detail": {
            "current": 5,
            "limit": 5,
            "plan": "free",
        },
    }
    await db_session.close()


@pytest.mark.asyncio
async def test_create_invite_ignores_inactive_members_for_plan_limit(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)
    data["workspace"].plan = WorkspacePlan.FREE

    extra_active = User(
        telegram_id=7_850_000_001 + (uuid4().int % 100_000),
        full_name="Extra Active Member",
        username="extra_active_member",
    )
    extra_inactive = User(
        telegram_id=7_850_000_002 + (uuid4().int % 100_000),
        full_name="Extra Inactive Member",
        username="extra_inactive_member",
    )
    db_session.add_all([extra_active, extra_inactive])
    await db_session.flush()
    db_session.add_all(
        [
            WorkspaceMember(
                workspace_id=data["workspace"].id,
                user_id=extra_active.id,
                role=WorkspaceRole.CLIENT,
                is_active=True,
                joined_at=datetime(2026, 1, 10, 11, 0, tzinfo=UTC),
            ),
            WorkspaceMember(
                workspace_id=data["workspace"].id,
                user_id=extra_inactive.id,
                role=WorkspaceRole.CLIENT,
                is_active=False,
                joined_at=datetime(2026, 1, 10, 11, 5, tzinfo=UTC),
            ),
        ]
    )
    await db_session.commit()

    response = await client.post(
        f"/workspaces/{data['workspace'].id}/invites",
        json={"role": "assistant"},
        headers=_auth_headers(data["admin"]),
    )

    assert response.status_code == 201
    assert response.json()["role"] == "assistant"
    await db_session.close()


@pytest.mark.asyncio
async def test_get_invite_returns_public_info(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)
    invite = WorkspaceInvite(
        workspace_id=data["workspace"].id,
        role=WorkspaceRole.ASSISTANT,
        created_by_user_id=data["admin"].id,
        expires_at=datetime.now(UTC) + timedelta(days=2),
    )
    db_session.add(invite)
    await db_session.commit()
    await db_session.refresh(invite)

    response = await client.get(f"/invites/{invite.token}")

    assert response.status_code == 200
    assert response.json()["workspace_title"] == data["workspace"].title
    assert response.json()["role"] == "assistant"
    assert response.json()["group_id"] is None
    await db_session.close()


@pytest.mark.asyncio
async def test_accept_invite_creates_workspace_member(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)
    invite = WorkspaceInvite(
        workspace_id=data["workspace"].id,
        role=WorkspaceRole.ASSISTANT,
        created_by_user_id=data["admin"].id,
        expires_at=datetime.now(UTC) + timedelta(days=2),
    )
    db_session.add(invite)
    await db_session.commit()
    await db_session.refresh(invite)

    response = await client.post(
        f"/invites/{invite.token}/accept",
        headers=_auth_headers(data["invitee"]),
    )

    assert response.status_code == 200
    assert response.json() == {
        "workspace_id": str(data["workspace"].id),
        "workspace_title": data["workspace"].title,
        "role": "assistant",
    }

    member = await db_session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == data["workspace"].id,
            WorkspaceMember.user_id == data["invitee"].id,
        )
    )
    assert member is not None
    assert member.role == WorkspaceRole.ASSISTANT
    assert member.is_active is True

    await db_session.refresh(invite)
    assert invite.used_by_user_id == data["invitee"].id
    assert invite.used_at is not None
    await db_session.close()


@pytest.mark.asyncio
async def test_accept_used_invite_returns_conflict(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)
    invite = WorkspaceInvite(
        workspace_id=data["workspace"].id,
        role=WorkspaceRole.ASSISTANT,
        created_by_user_id=data["admin"].id,
        expires_at=datetime.now(UTC) + timedelta(days=2),
        used_at=datetime.now(UTC),
        used_by_user_id=data["invitee"].id,
    )
    db_session.add(invite)
    await db_session.commit()
    await db_session.refresh(invite)

    response = await client.post(
        f"/invites/{invite.token}/accept",
        headers=_auth_headers(data["outsider"]),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Invite token has already been used"}
    await db_session.close()


@pytest.mark.asyncio
async def test_get_expired_invite_returns_gone(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)
    invite = WorkspaceInvite(
        workspace_id=data["workspace"].id,
        role=WorkspaceRole.ASSISTANT,
        created_by_user_id=data["admin"].id,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db_session.add(invite)
    await db_session.commit()
    await db_session.refresh(invite)

    response = await client.get(f"/invites/{invite.token}")

    assert response.status_code == 410
    assert response.json() == {"detail": "Invite token has expired"}
    await db_session.close()


@pytest.mark.asyncio
async def test_revoke_invite_removes_it_from_active_list(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)
    invite = WorkspaceInvite(
        workspace_id=data["workspace"].id,
        role=WorkspaceRole.ASSISTANT,
        created_by_user_id=data["admin"].id,
        expires_at=datetime.now(UTC) + timedelta(days=2),
    )
    db_session.add(invite)
    await db_session.commit()
    await db_session.refresh(invite)

    delete_response = await client.delete(
        f"/workspaces/{data['workspace'].id}/invites/{invite.token}",
        headers=_auth_headers(data["admin"]),
    )

    assert delete_response.status_code == 204

    list_response = await client.get(
        f"/workspaces/{data['workspace'].id}/invites",
        headers=_auth_headers(data["admin"]),
    )

    assert list_response.status_code == 200
    assert list_response.json() == []
    await db_session.close()


@pytest.mark.asyncio
async def test_accept_invite_reactivates_inactive_membership_and_updates_role(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)
    inactive_member = WorkspaceMember(
        workspace_id=data["workspace"].id,
        user_id=data["invitee"].id,
        role=WorkspaceRole.CLIENT,
        is_active=False,
        joined_at=datetime(2026, 1, 10, 10, 15, tzinfo=UTC),
    )
    invite = WorkspaceInvite(
        workspace_id=data["workspace"].id,
        role=WorkspaceRole.WORKSPACE_ADMIN,
        created_by_user_id=data["admin"].id,
        expires_at=datetime.now(UTC) + timedelta(days=2),
    )
    db_session.add_all([inactive_member, invite])
    await db_session.commit()
    await db_session.refresh(invite)

    response = await client.post(
        f"/invites/{invite.token}/accept",
        headers=_auth_headers(data["invitee"]),
    )

    assert response.status_code == 200
    assert response.json() == {
        "workspace_id": str(data["workspace"].id),
        "workspace_title": data["workspace"].title,
        "role": "workspace_admin",
    }

    member = await db_session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == data["workspace"].id,
            WorkspaceMember.user_id == data["invitee"].id,
        )
    )
    assert member is not None
    await db_session.refresh(member)
    assert member.role == WorkspaceRole.WORKSPACE_ADMIN
    assert member.is_active is True
    await db_session.close()


@pytest.mark.asyncio
async def test_client_invite_must_target_group(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)

    response = await client.post(
        f"/workspaces/{data['workspace'].id}/invites",
        json={"role": "client"},
        headers=_auth_headers(data["admin"]),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "client invite must target a group"}
    await db_session.close()


@pytest.mark.asyncio
async def test_create_client_invite_with_group_and_accept_creates_group_member(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)

    create_response = await client.post(
        f"/workspaces/{data['workspace'].id}/invites",
        json={"role": "client", "group_id": str(data["group"].id)},
        headers=_auth_headers(data["admin"]),
    )

    assert create_response.status_code == 201
    assert create_response.json()["group_id"] == str(data["group"].id)
    token = create_response.json()["token"]

    accept_response = await client.post(
        f"/invites/{token}/accept",
        headers=_auth_headers(data["invitee"]),
    )

    assert accept_response.status_code == 200

    group_member = await db_session.scalar(
        select(GroupMember).where(
            GroupMember.group_id == data["group"].id,
            GroupMember.user_id == data["invitee"].id,
        )
    )
    assert group_member is not None
    assert group_member.role == GroupMemberRole.CLIENT
    assert group_member.is_active is True
    await db_session.close()
