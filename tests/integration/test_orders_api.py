from uuid import UUID

import pytest
from httpx import AsyncClient

from tests.support import RecordingBroker

pytestmark = pytest.mark.integration


async def create_account(client: AsyncClient, payload: dict) -> dict:
    response = await client.post("/api/v1/accounts", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_get_list_and_cancel_order(
    api_client: AsyncClient,
    account_payload: dict,
    recording_broker: RecordingBroker,
) -> None:
    account = await create_account(api_client, account_payload)
    order_payload = {
        "client_order_id": "CLIENT-ORDER-1",
        "idempotency_key": "idem-client-order-1",
        "account_id": account["id"],
        "symbol": "RELIANCE",
        "side": "BUY",
        "order_type": "LIMIT",
        "time_in_force": "GTC",
        "quantity": "100",
        "price": "100.50",
    }

    response = await api_client.post("/api/v1/orders", json=order_payload)
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["status"] == "ROUTED"
    assert order["remaining_quantity"] == "100.00000000"
    assert len(recording_broker.submitted_orders) == 1

    repeated = await api_client.post("/api/v1/orders", json=order_payload)
    assert repeated.status_code == 201
    assert repeated.json()["id"] == order["id"]
    assert len(recording_broker.submitted_orders) == 1

    fetched = await api_client.get(f"/api/v1/orders/{order['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["client_order_id"] == "CLIENT-ORDER-1"

    open_orders = await api_client.get(
        "/api/v1/orders",
        params={"account_id": account["id"], "open_only": "true"},
    )
    assert open_orders.status_code == 200
    assert [item["id"] for item in open_orders.json()] == [order["id"]]

    cancelled = await api_client.post(f"/api/v1/orders/{order['id']}/cancel")
    assert cancelled.status_code == 202
    assert cancelled.json()["status"] == "CANCEL_PENDING"
    assert recording_broker.cancelled_orders == [
        (UUID(order["id"]), "Client requested cancellation")
    ]


async def test_insufficient_buying_power_creates_rejected_audit_order(
    api_client: AsyncClient,
    account_payload: dict,
) -> None:
    account = await create_account(api_client, account_payload)
    response = await api_client.post(
        "/api/v1/orders",
        json={
            "client_order_id": "TOO-LARGE",
            "idempotency_key": "idem-too-large-order",
            "account_id": account["id"],
            "symbol": "NIFTY",
            "side": "BUY",
            "order_type": "LIMIT",
            "time_in_force": "DAY",
            "quantity": "1000",
            "price": "1000",
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "REJECTED"
    assert response.json()["rejection_reason"] == "Insufficient buying power"

    events = await api_client.get(
        f"/api/v1/orders/{response.json()['id']}/events"
    )
    assert events.status_code == 200
    assert [event["event_type"] for event in events.json()] == [
        "ORDER_CREATED",
        "VALIDATION_FAILED",
    ]
