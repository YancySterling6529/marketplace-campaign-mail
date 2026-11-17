import json

from src.marketplace_mail import BuyerUpdate, InfraiClient, SellerAsset, handoff_asset


def test_open_event_moves_order_handoff_to_opened() -> None:
    calls = []

    def transport(request):
        calls.append((request.method, request.full_url, json.loads(request.data.decode()) if request.data else None))
        if request.method == "POST":
            return 200, {}, b'{"ok":true,"data":{"message_id":"msg-7"}}'
        return 200, {}, b'{"ok":true,"data":[{"event":"open"}]}'

    client = InfraiClient(api_key="test-key", transport=transport)
    result = handoff_asset(
        client,
        SellerAsset("Seller", "Lamp", "buyer@example.com", "42"),
        BuyerUpdate("Handoff", "The seller is ready."),
    )

    assert result.status == "opened"
    assert calls[0][0] == "POST"
    assert calls[0][2] == {
        "to": "buyer@example.com",
        "subject": "Handoff",
        "body": "The seller is ready.",
        "idempotency_key": "order-42",
    }
    assert calls[1][0] == "GET"
    assert "message_id=msg-7" in calls[1][1]
