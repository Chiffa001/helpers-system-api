from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WorkspaceEventAudience, WorkspaceRole
from app.models.workspace_event import WorkspaceEvent
from app.models.workspace_event_participant import WorkspaceEventParticipant
from app.models.workspace_invite import WorkspaceInvite
from tests.test_groups import _auth_headers, _seed_groups_data
from tests.test_invites import _seed_invite_data


@pytest.mark.asyncio
async def test_workspace_admin_can_create_and_list_workspace_events(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_groups_data(db_session)

    create_response = await client.post(
        f"/workspaces/{data['workspace'].id}/events",
        json={
            "title": "Assistants Sync",
            "description": "Weekly sync-up",
            "date": "2026-05-20T11:00:00Z",
            "location": "Zoom",
            "audience": "assistants",
            "group_ids": [str(data["assistant_group"].id), str(data["assistant_group"].id)],
        },
        headers=_auth_headers(data["admin"]),
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["audience"] == "assistants"
    assert created["group_ids"] == [str(data["assistant_group"].id)]
    assert created["participants_summary"] == {
        "total": 2,
        "accepted": 0,
        "declined": 0,
        "pending": 2,
    }
    assert created["my_response"] is None

    list_response = await client.get(
        f"/workspaces/{data['workspace'].id}/events",
        headers=_auth_headers(data["admin"]),
    )

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [created["id"]]

    assistant_detail = await client.get(
        f"/workspace-events/{created['id']}",
        headers=_auth_headers(data["assistant"]),
    )
    assert assistant_detail.status_code == 200
    assert assistant_detail.json()["my_response"] == "pending"
    assert assistant_detail.json()["participants_summary"] is None

    client_detail = await client.get(
        f"/workspace-events/{created['id']}",
        headers=_auth_headers(data["client"]),
    )
    assert client_detail.status_code == 403
    assert client_detail.json() == {"detail": "access denied"}


@pytest.mark.asyncio
async def test_workspace_event_reactions_and_participants_are_visible_to_admin(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_groups_data(db_session)

    create_response = await client.post(
        f"/workspaces/{data['workspace'].id}/events",
        json={
            "title": "General Meeting",
            "date": "2026-05-22T10:00:00Z",
            "audience": "all",
        },
        headers=_auth_headers(data["admin"]),
    )
    assert create_response.status_code == 201
    event_id = create_response.json()["id"]

    accept_response = await client.post(
        f"/workspace-events/{event_id}/accept",
        headers=_auth_headers(data["assistant"]),
    )
    assert accept_response.status_code == 200
    assert accept_response.json() == {"response": "accepted"}

    decline_response = await client.post(
        f"/workspace-events/{event_id}/decline",
        headers=_auth_headers(data["assistant"]),
    )
    assert decline_response.status_code == 200
    assert decline_response.json() == {"response": "declined"}

    participants_response = await client.get(
        f"/workspace-events/{event_id}/participants",
        headers=_auth_headers(data["admin"]),
    )
    assert participants_response.status_code == 200
    participants = participants_response.json()
    assert len(participants) == 4
    assistant_row = next(
        item for item in participants if item["user_id"] == str(data["assistant"].id)
    )
    assert assistant_row["role"] == "assistant"
    assert assistant_row["response"] == "declined"
    assert assistant_row["responded_at"] is not None

    declined_participants_response = await client.get(
        f"/workspace-events/{event_id}/participants",
        params={"response": "declined"},
        headers=_auth_headers(data["admin"]),
    )
    assert declined_participants_response.status_code == 200
    assert declined_participants_response.json() == [assistant_row]

    admin_detail = await client.get(
        f"/workspace-events/{event_id}",
        headers=_auth_headers(data["admin"]),
    )
    assert admin_detail.status_code == 200
    assert admin_detail.json()["participants_summary"] == {
        "total": 4,
        "accepted": 0,
        "declined": 1,
        "pending": 3,
    }


@pytest.mark.asyncio
async def test_workspace_event_group_bindings_and_lifecycle_rules(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_groups_data(db_session)

    create_response = await client.post(
        f"/workspaces/{data['workspace'].id}/events",
        json={
            "title": "Workspace Standup",
            "date": "2026-05-24T09:00:00Z",
            "audience": "all",
        },
        headers=_auth_headers(data["admin"]),
    )
    assert create_response.status_code == 201
    event_id = create_response.json()["id"]

    add_groups_response = await client.post(
        f"/workspace-events/{event_id}/groups",
        json={
            "group_ids": [
                str(data["assistant_group"].id),
                str(data["other_group"].id),
                str(data["assistant_group"].id),
            ]
        },
        headers=_auth_headers(data["admin"]),
    )
    assert add_groups_response.status_code == 200
    assert sorted(add_groups_response.json()["group_ids"]) == sorted(
        [str(data["assistant_group"].id), str(data["other_group"].id)]
    )

    filtered_response = await client.get(
        f"/workspaces/{data['workspace'].id}/events",
        params={"group_id": str(data["assistant_group"].id)},
        headers=_auth_headers(data["assistant"]),
    )
    assert filtered_response.status_code == 200
    assert [item["id"] for item in filtered_response.json()] == [event_id]

    remove_group_response = await client.delete(
        f"/workspace-events/{event_id}/groups/{data['other_group'].id}",
        headers=_auth_headers(data["admin"]),
    )
    assert remove_group_response.status_code == 204

    cancel_response = await client.post(
        f"/workspace-events/{event_id}/cancel",
        headers=_auth_headers(data["admin"]),
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    edit_cancelled_response = await client.patch(
        f"/workspace-events/{event_id}",
        json={"title": "Renamed"},
        headers=_auth_headers(data["admin"]),
    )
    assert edit_cancelled_response.status_code == 409
    assert edit_cancelled_response.json() == {"detail": "event is not editable"}

    delete_cancelled_response = await client.delete(
        f"/workspace-events/{event_id}",
        headers=_auth_headers(data["admin"]),
    )
    assert delete_cancelled_response.status_code == 409
    assert delete_cancelled_response.json() == {"detail": "only upcoming events can be deleted"}


@pytest.mark.asyncio
async def test_workspace_event_create_validates_future_date_and_group_scope(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_groups_data(db_session)
    other_workspace_data = await _seed_groups_data(db_session)

    past_date_response = await client.post(
        f"/workspaces/{data['workspace'].id}/events",
        json={
            "title": "Past Event",
            "date": "2026-01-01T10:00:00Z",
            "audience": "all",
        },
        headers=_auth_headers(data["admin"]),
    )
    assert past_date_response.status_code == 422
    assert past_date_response.json() == {"detail": "date must be in the future"}

    wrong_group_scope_response = await client.post(
        f"/workspaces/{data['workspace'].id}/events",
        json={
            "title": "Scoped Event",
            "date": "2026-05-24T09:00:00Z",
            "audience": "all",
            "group_ids": [str(other_workspace_data["assistant_group"].id)],
        },
        headers=_auth_headers(data["admin"]),
    )
    assert wrong_group_scope_response.status_code == 422
    assert wrong_group_scope_response.json() == {"detail": "group not found in workspace"}


@pytest.mark.asyncio
async def test_accepting_invite_adds_participant_to_matching_upcoming_workspace_events(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_invite_data(db_session)

    event = WorkspaceEvent(
        workspace_id=data["workspace"].id,
        title="Assistants Training",
        date=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        audience=WorkspaceEventAudience.ASSISTANTS,
        created_by_user_id=data["admin"].id,
    )
    invite = WorkspaceInvite(
        workspace_id=data["workspace"].id,
        role=WorkspaceRole.ASSISTANT,
        created_by_user_id=data["admin"].id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(event)
    await db_session.flush()
    db_session.add(invite)
    await db_session.commit()

    accept_response = await client.post(
        f"/invites/{invite.token}/accept",
        headers=_auth_headers(data["invitee"]),
    )
    assert accept_response.status_code == 200

    participant = await db_session.scalar(
        select(WorkspaceEventParticipant).where(
            WorkspaceEventParticipant.workspace_event_id == event.id,
            WorkspaceEventParticipant.user_id == data["invitee"].id,
        )
    )
    assert participant is not None
    assert participant.response.value == "pending"
    await db_session.close()


@pytest.mark.asyncio
async def test_group_events_feed_aggregates_group_and_workspace_events(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_groups_data(db_session)

    group_event_response = await client.post(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/events",
        json={
            "title": "Group Consultation",
            "date": "2026-06-05T10:00:00Z",
            "is_paid": False,
        },
        headers=_auth_headers(data["assistant"]),
    )
    assert group_event_response.status_code == 201

    workspace_event_response = await client.post(
        f"/workspaces/{data['workspace'].id}/events",
        json={
            "title": "Workspace Briefing",
            "date": "2026-06-06T10:00:00Z",
            "audience": "all",
            "group_ids": [str(data["assistant_group"].id)],
        },
        headers=_auth_headers(data["admin"]),
    )
    assert workspace_event_response.status_code == 201

    admin_feed_response = await client.get(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/events/feed",
        headers=_auth_headers(data["admin"]),
    )
    assert admin_feed_response.status_code == 200
    admin_feed = admin_feed_response.json()
    assert admin_feed["total"] == 2
    assert [item["type"] for item in admin_feed["items"]] == ["group", "workspace"]
    assert admin_feed["items"][1]["participants_summary"] == {
        "total": 4,
        "accepted": 0,
        "declined": 0,
        "pending": 4,
    }

    client_feed_response = await client.get(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/events/feed",
        headers=_auth_headers(data["client"]),
    )
    assert client_feed_response.status_code == 200
    client_feed = client_feed_response.json()
    assert client_feed["total"] == 2
    assert client_feed["items"][1]["my_response"] == "pending"
    assert client_feed["items"][1]["participants_summary"] is None

    workspace_only_response = await client.get(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/events/feed",
        params={"type": "workspace"},
        headers=_auth_headers(data["assistant"]),
    )
    assert workspace_only_response.status_code == 200
    assert workspace_only_response.json()["total"] == 1
    assert workspace_only_response.json()["items"][0]["type"] == "workspace"


@pytest.mark.asyncio
async def test_workspace_events_list_respects_filters_sorting_and_role_restrictions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_groups_data(db_session)

    first_response = await client.post(
        f"/workspaces/{data['workspace'].id}/events",
        json={
            "title": "Completed Earlier",
            "date": "2026-06-10T10:00:00Z",
            "audience": "all",
        },
        headers=_auth_headers(data["admin"]),
    )
    second_response = await client.post(
        f"/workspaces/{data['workspace'].id}/events",
        json={
            "title": "Completed Later",
            "date": "2026-06-12T10:00:00Z",
            "audience": "all",
        },
        headers=_auth_headers(data["admin"]),
    )
    assistants_response = await client.post(
        f"/workspaces/{data['workspace'].id}/events",
        json={
            "title": "Assistants Only",
            "date": "2026-06-14T10:00:00Z",
            "audience": "assistants",
        },
        headers=_auth_headers(data["admin"]),
    )
    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert assistants_response.status_code == 201

    first_id = first_response.json()["id"]
    second_id = second_response.json()["id"]

    complete_first = await client.post(
        f"/workspace-events/{first_id}/complete",
        headers=_auth_headers(data["admin"]),
    )
    complete_second = await client.post(
        f"/workspace-events/{second_id}/complete",
        headers=_auth_headers(data["admin"]),
    )
    assert complete_first.status_code == 200
    assert complete_second.status_code == 200

    completed_list_response = await client.get(
        f"/workspaces/{data['workspace'].id}/events",
        params={"status": "completed"},
        headers=_auth_headers(data["admin"]),
    )
    assert completed_list_response.status_code == 200
    assert [item["title"] for item in completed_list_response.json()] == [
        "Completed Later",
        "Completed Earlier",
    ]

    audience_filtered_response = await client.get(
        f"/workspaces/{data['workspace'].id}/events",
        params={"audience": "assistants"},
        headers=_auth_headers(data["admin"]),
    )
    assert audience_filtered_response.status_code == 200
    assert [item["title"] for item in audience_filtered_response.json()] == ["Assistants Only"]

    forbidden_audience_filter_response = await client.get(
        f"/workspaces/{data['workspace'].id}/events",
        params={"audience": "assistants"},
        headers=_auth_headers(data["assistant"]),
    )
    assert forbidden_audience_filter_response.status_code == 403
    assert forbidden_audience_filter_response.json() == {
        "detail": "Audience filter is not available for your role"
    }


@pytest.mark.asyncio
async def test_workspace_event_rejects_non_participants_and_missing_group_bindings(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_groups_data(db_session)

    create_response = await client.post(
        f"/workspaces/{data['workspace'].id}/events",
        json={
            "title": "Admins Only",
            "date": "2026-06-20T10:00:00Z",
            "audience": "admins",
        },
        headers=_auth_headers(data["admin"]),
    )
    assert create_response.status_code == 201
    event_id = create_response.json()["id"]

    assistant_accept_response = await client.post(
        f"/workspace-events/{event_id}/accept",
        headers=_auth_headers(data["assistant"]),
    )
    assert assistant_accept_response.status_code == 403
    assert assistant_accept_response.json() == {"detail": "access denied"}

    missing_binding_response = await client.delete(
        f"/workspace-events/{event_id}/groups/{data['assistant_group'].id}",
        headers=_auth_headers(data["admin"]),
    )
    assert missing_binding_response.status_code == 404
    assert missing_binding_response.json() == {"detail": "Workspace event group binding not found"}


@pytest.mark.asyncio
async def test_group_events_feed_respects_type_status_sorting_and_audience_visibility(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    data = await _seed_groups_data(db_session)

    first_group_response = await client.post(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/events",
        json={
            "title": "Old Group Event",
            "date": "2026-06-01T10:00:00Z",
            "is_paid": False,
        },
        headers=_auth_headers(data["assistant"]),
    )
    second_group_response = await client.post(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/events",
        json={
            "title": "New Group Event",
            "date": "2026-06-03T10:00:00Z",
            "is_paid": False,
        },
        headers=_auth_headers(data["assistant"]),
    )
    assistants_workspace_response = await client.post(
        f"/workspaces/{data['workspace'].id}/events",
        json={
            "title": "Assistants Group Briefing",
            "date": "2026-06-04T10:00:00Z",
            "audience": "assistants",
            "group_ids": [str(data["assistant_group"].id)],
        },
        headers=_auth_headers(data["admin"]),
    )
    assert first_group_response.status_code == 201
    assert second_group_response.status_code == 201
    assert assistants_workspace_response.status_code == 201

    old_group_event_id = first_group_response.json()["id"]
    new_group_event_id = second_group_response.json()["id"]

    update_old_group = await client.patch(
        f"/workspaces/{data['workspace'].id}/groups/"
        f"{data['assistant_group'].id}/events/{old_group_event_id}",
        json={"status": "completed"},
        headers=_auth_headers(data["admin"]),
    )
    update_new_group = await client.patch(
        f"/workspaces/{data['workspace'].id}/groups/"
        f"{data['assistant_group'].id}/events/{new_group_event_id}",
        json={"status": "completed"},
        headers=_auth_headers(data["admin"]),
    )
    assert update_old_group.status_code == 200
    assert update_new_group.status_code == 200

    group_only_completed_response = await client.get(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/events/feed",
        params={"type": "group", "status": "completed"},
        headers=_auth_headers(data["admin"]),
    )
    assert group_only_completed_response.status_code == 200
    assert [item["title"] for item in group_only_completed_response.json()["items"]] == [
        "New Group Event",
        "Old Group Event",
    ]

    client_workspace_feed_response = await client.get(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/events/feed",
        params={"type": "workspace"},
        headers=_auth_headers(data["client"]),
    )
    assert client_workspace_feed_response.status_code == 200
    assert client_workspace_feed_response.json() == {"items": [], "total": 0}
