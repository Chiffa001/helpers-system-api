from decimal import Decimal

import pytest
from httpx import AsyncClient

from tests.test_groups import _auth_headers, _seed_groups_data


@pytest.mark.asyncio
async def test_assistant_can_manage_documents_and_client_can_view_them(
    client: AsyncClient,
    db_session,
) -> None:
    data = await _seed_groups_data(db_session)

    create_response = await client.post(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/documents",
        json={
            "title": "Brief",
            "body": "Important notes",
        },
        headers=_auth_headers(data["assistant"]),
    )

    assert create_response.status_code == 201

    list_response = await client.get(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/documents",
        headers=_auth_headers(data["client"]),
    )

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["title"] == "Brief"


@pytest.mark.asyncio
async def test_client_cannot_create_group_stage_but_can_list_stages(
    client: AsyncClient,
    db_session,
) -> None:
    data = await _seed_groups_data(db_session)

    create_response = await client.post(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/stages",
        json={"title": "Collect docs"},
        headers=_auth_headers(data["assistant"]),
    )

    assert create_response.status_code == 201

    list_response = await client.get(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/stages",
        headers=_auth_headers(data["client"]),
    )

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["status"] == "todo"

    forbidden_response = await client.patch(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/stages/{create_response.json()['id']}",
        json={"status": "done"},
        headers=_auth_headers(data["client"]),
    )

    assert forbidden_response.status_code == 403
    assert forbidden_response.json() == {"detail": "Insufficient group permissions"}


@pytest.mark.asyncio
async def test_stage_status_change_and_event_creation_are_written_to_history(
    client: AsyncClient,
    db_session,
) -> None:
    data = await _seed_groups_data(db_session)

    stage_response = await client.post(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/stages",
        json={"title": "Prepare plan"},
        headers=_auth_headers(data["assistant"]),
    )
    assert stage_response.status_code == 201

    update_stage_response = await client.patch(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/stages/{stage_response.json()['id']}",
        json={"status": "in_progress"},
        headers=_auth_headers(data["assistant"]),
    )
    assert update_stage_response.status_code == 200

    event_response = await client.post(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/events",
        json={
            "title": "Consultation",
            "date": "2026-05-10T12:00:00Z",
            "is_paid": False,
        },
        headers=_auth_headers(data["assistant"]),
    )
    assert event_response.status_code == 201

    cancel_event_response = await client.patch(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/events/{event_response.json()['id']}",
        json={"status": "cancelled"},
        headers=_auth_headers(data["admin"]),
    )
    assert cancel_event_response.status_code == 200

    history_response = await client.get(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/history",
        headers=_auth_headers(data["assistant"]),
    )

    assert history_response.status_code == 200
    event_types = [item["event_type"] for item in history_response.json()]
    assert "stage_status_changed" in event_types
    assert "event_created" in event_types
    assert "event_cancelled" in event_types


@pytest.mark.asyncio
async def test_invoice_flow_respects_roles_and_writes_history(
    client: AsyncClient,
    db_session,
) -> None:
    data = await _seed_groups_data(db_session)

    event_response = await client.post(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/events",
        json={
            "title": "Paid Session",
            "date": "2026-05-12T14:00:00Z",
            "is_paid": True,
            "amount": "5000.00",
            "currency": "RUB",
        },
        headers=_auth_headers(data["assistant"]),
    )
    assert event_response.status_code == 201

    invoice_response = await client.post(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/invoices",
        json={
            "group_event_id": event_response.json()["id"],
            "client_user_id": str(data["client"].id),
            "amount": "5000.00",
            "due_date": "2026-05-20T00:00:00Z",
        },
        headers=_auth_headers(data["assistant"]),
    )
    assert invoice_response.status_code == 201
    invoice_id = invoice_response.json()["id"]
    assert Decimal(invoice_response.json()["amount"]) == Decimal("5000.00")

    client_list_response = await client.get(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/invoices",
        headers=_auth_headers(data["client"]),
    )
    assert client_list_response.status_code == 200
    assert len(client_list_response.json()) == 1
    assert client_list_response.json()[0]["id"] == invoice_id

    pay_response = await client.post(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/invoices/{invoice_id}/pay",
        json={"tx_hash": "0xabc123"},
        headers=_auth_headers(data["client"]),
    )
    assert pay_response.status_code == 200
    assert pay_response.json()["status"] == "pending_payment"

    assistant_paid_response = await client.patch(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/invoices/{invoice_id}",
        json={"status": "paid"},
        headers=_auth_headers(data["assistant"]),
    )
    assert assistant_paid_response.status_code == 403
    assert assistant_paid_response.json() == {
        "detail": "Assistant cannot manually confirm invoice payment"
    }

    admin_paid_response = await client.patch(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/invoices/{invoice_id}",
        json={"status": "paid"},
        headers=_auth_headers(data["admin"]),
    )
    assert admin_paid_response.status_code == 200
    assert admin_paid_response.json()["status"] == "paid"
    assert admin_paid_response.json()["paid_at"] is not None

    history_response = await client.get(
        f"/workspaces/{data['workspace'].id}/groups/{data['assistant_group'].id}/history",
        headers=_auth_headers(data["admin"]),
    )
    assert history_response.status_code == 200
    event_types = [item["event_type"] for item in history_response.json()]
    assert "invoice_issued" in event_types
    assert "invoice_paid" in event_types


@pytest.mark.asyncio
async def test_client_cannot_access_other_group_history(
    client: AsyncClient,
    db_session,
) -> None:
    data = await _seed_groups_data(db_session)

    response = await client.get(
        f"/workspaces/{data['workspace'].id}/groups/{data['other_group'].id}/history",
        headers=_auth_headers(data["client"]),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Group access denied"}
