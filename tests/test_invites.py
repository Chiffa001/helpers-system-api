from datetime import UTC, datetime, timedelta
from typing import TypedDict
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.enums import WorkspaceRole
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_invite import WorkspaceInvite
from app.models.workspace_member import WorkspaceMember


class SeededInviteData(TypedDict):
    workspace: Workspace
    admin: User
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
        mini_app_url="https://t.me/ClinicBot/App",
    )
    admin = User(
        telegram_id=7_810_000_000 + telegram_seed,
        full_name="Workspace Admin",
        username="workspace_admin",
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

    db_session.add_all([workspace, admin, invitee, outsider])
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
    assert created["invite_url"] == f"https://t.me/ClinicBot/App?startapp=invite_{created['token']}"

    list_response = await client.get(
        f"/workspaces/{data['workspace'].id}/invites",
        headers=_auth_headers(data["admin"]),
    )

    assert list_response.status_code == 200
    assert list_response.json() == [created]
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
