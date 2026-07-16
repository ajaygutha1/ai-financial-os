import secrets
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.exceptions import UnauthorizedError
from app.core.redis import get_async_redis_client, get_redis_client
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/events", tags=["events"])

_TICKET_TTL_SECONDS = 30
_TICKET_KEY_PREFIX = "sse_ticket:"
_KEEPALIVE_INTERVAL_SECONDS = 15


@router.post("/ticket")
def issue_sse_ticket(current_user: User = Depends(get_current_user)) -> dict[str, str]:
    """A short-lived, single-use ticket for the SSE stream below.
    `EventSource` can't send a custom Authorization header, so the normal
    bearer access token can't be used directly -- and putting a real
    15-minute-lived JWT in a URL (which browsers, proxies, and access logs
    routinely record) is a worse tradeoff than a ticket that's dead within
    seconds, whichever comes first: 30s TTL or first use."""
    ticket = secrets.token_urlsafe(32)
    client = get_redis_client()
    client.setex(f"{_TICKET_KEY_PREFIX}{ticket}", _TICKET_TTL_SECONDS, str(current_user.id))
    return {"ticket": ticket}


async def _consume_ticket(ticket: str) -> uuid.UUID:
    client = get_async_redis_client()
    user_id_str = await client.getdel(f"{_TICKET_KEY_PREFIX}{ticket}")
    if user_id_str is None:
        raise UnauthorizedError("Invalid or expired stream ticket.")
    return uuid.UUID(user_id_str)


async def _event_stream(user_id: uuid.UUID) -> AsyncIterator[str]:
    client = get_async_redis_client()
    pubsub = client.pubsub()
    channel = f"domain_events.user.{user_id}"
    await pubsub.subscribe(channel)
    try:
        # Confirms the connection is live immediately, rather than the
        # client waiting up to a full keepalive interval to know the stream
        # actually opened.
        yield ": connected\n\n"
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=_KEEPALIVE_INTERVAL_SECONDS
            )
            if message is not None:
                yield f"data: {message['data']}\n\n"
            else:
                # An SSE comment line -- ignored by EventSource's message
                # parsing, just keeps intermediary proxies/load balancers
                # from treating the connection as idle and closing it.
                yield ": ping\n\n"
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()  # type: ignore[no-untyped-call]


@router.get("/stream")
async def stream_events(ticket: str = Query(...)) -> StreamingResponse:
    user_id = await _consume_ticket(ticket)
    return StreamingResponse(
        _event_stream(user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
