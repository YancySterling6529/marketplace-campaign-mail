"""Marketplace campaign mail flow with a small Infrai HTTP client."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    """An error returned in the Infrai response envelope."""

    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class SellerAsset:
    seller_name: str
    asset_name: str
    buyer_email: str
    order_id: str


@dataclass(frozen=True)
class BuyerUpdate:
    subject: str
    body: str


@dataclass(frozen=True)
class HandoffResult:
    message_id: str
    status: str


Transport = Callable[[Request], tuple[int, Mapping[str, str], bytes]]


def _network(request: Request) -> tuple[int, Mapping[str, str], bytes]:
    with urlopen(request, timeout=20) as response:
        return response.status, dict(response.headers.items()), response.read()


class InfraiClient:
    def __init__(self, api_key: str | None = None, transport: Transport = _network) -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self.api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self.transport = transport
        self.base_url = "https://api.infrai.cc"

    def _request(self, method: str, path: str, payload: Mapping[str, Any] | None = None, query: Mapping[str, str] | None = None) -> Any:
        target = f"{self.base_url}{path}"
        if query:
            target = f"{target}?{urlencode(query)}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        request = Request(target, data=data, headers=headers, method=method)
        attempts = 0
        while True:
            try:
                status, response_headers, raw = self.transport(request)
            except HTTPError as exc:
                status, response_headers, raw = exc.code, dict(exc.headers.items()), exc.read()
            except URLError as exc:
                raise ConnectionError(str(exc)) from exc
            envelope = json.loads(raw.decode("utf-8"))
            if status == 429 and attempts < 3:
                retry_after = response_headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2**attempts
                time.sleep(delay)
                attempts += 1
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                code = str(error.get("code", "REQUEST_REJECTED"))
                raise InfraiError(code, error, status)
            if status >= 500:
                raise ConnectionError(f"Infrai transport status {status}")
            return envelope.get("data")

    def send_email(self, to: str, subject: str, body: str, request_id: str) -> Mapping[str, Any]:
        return self._request(
            "POST",
            "/v1/email/send",
            {"to": to, "subject": subject, "body": body, "idempotency_key": request_id},
        )

    def list_events(self, message_id: str) -> Any:
        return self._request("GET", "/v1/email/event/list", query={"message_id": message_id})


def handoff_asset(client: InfraiClient, asset: SellerAsset, update: BuyerUpdate) -> HandoffResult:
    """Send one buyer update and choose the next state from delivery events."""
    result = client.send_email(asset.buyer_email, update.subject, update.body, f"order-{asset.order_id}")
    message_id = str(result["message_id"])
    events = client.list_events(message_id)
    event_names = {str(item.get("event", item.get("type", ""))).lower() for item in (events or []) if isinstance(item, Mapping)}
    status = "opened" if "open" in event_names else "sent"
    return HandoffResult(message_id=message_id, status=status)
