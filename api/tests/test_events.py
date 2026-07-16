import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import UnauthorizedError
from app.routers.v1.events import _consume_ticket, stream_events


def test_issue_ticket_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/events/ticket")
    assert response.status_code == 401


def test_issue_ticket_returns_a_ticket(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/v1/events/ticket", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["ticket"], str)
    assert len(body["ticket"]) > 20


# The remaining tests exercise the streaming logic directly as coroutines
# rather than through TestClient: an open-ended StreamingResponse body never
# completes until the client disconnects, and TestClient's in-process ASGI
# transport does not reliably propagate an early client-side close into
# server-side generator cancellation the way a real network connection
# would -- attempting to open the stream through TestClient hangs the test
# runner indefinitely. Calling the endpoint coroutine and iterating its
# body_iterator directly (with an explicit timeout) tests the same logic
# without depending on that transport behavior.


async def test_consume_ticket_resolves_the_user_id(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    ticket = client.post("/api/v1/events/ticket", headers=auth_headers).json()["ticket"]
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()

    user_id = await _consume_ticket(ticket)

    assert str(user_id) == me["id"]


async def test_consume_ticket_rejects_an_invalid_ticket() -> None:
    with pytest.raises(UnauthorizedError):
        await _consume_ticket("not-a-real-ticket")


async def test_consume_ticket_rejects_a_reused_ticket(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    ticket = client.post("/api/v1/events/ticket", headers=auth_headers).json()["ticket"]
    await _consume_ticket(ticket)

    with pytest.raises(UnauthorizedError):
        await _consume_ticket(ticket)


async def test_stream_events_yields_a_connected_message(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    ticket = client.post("/api/v1/events/ticket", headers=auth_headers).json()["ticket"]

    response = await stream_events(ticket=ticket)

    assert response.status_code == 200
    assert response.media_type == "text/event-stream"
    first_chunk = await asyncio.wait_for(anext(response.body_iterator), timeout=5)
    assert first_chunk == ": connected\n\n"
    await response.body_iterator.aclose()  # type: ignore[union-attr]


async def test_stream_events_rejects_an_invalid_ticket() -> None:
    with pytest.raises(UnauthorizedError):
        await stream_events(ticket="not-a-real-ticket")
