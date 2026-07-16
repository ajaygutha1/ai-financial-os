from functools import lru_cache

import redis
import redis.asyncio as redis_asyncio

from app.core.config import get_settings


@lru_cache
def get_redis_client() -> redis.Redis:
    settings = get_settings()
    # celery[redis]'s dependency pin forces an older `redis` package release
    # whose `from_url` loses its type info under mypy --strict; not our bug.
    return redis.from_url(settings.redis_url, decode_responses=True)  # type: ignore[no-any-return,no-untyped-call]


def get_async_redis_client() -> redis_asyncio.Redis:
    """Only the Milestone 7 SSE stream needs this -- everything else in this
    codebase is sync (matching the sync-SQLAlchemy style), but subscribing to
    a Redis pub/sub channel and awaiting messages inside a StreamingResponse
    generator needs a real async client, not a blocking one.

    Deliberately NOT `@lru_cache`'d, unlike the sync client above: an async
    client's connections are bound to the event loop that created them, so a
    cached singleton reused from a different loop (a new test, a worker
    restart) raises "RuntimeError: Event loop is closed" the moment it tries
    to use a connection from the dead loop. Constructing a fresh client is
    cheap -- `from_url` doesn't eagerly connect, it just configures a pool
    that connects lazily per command."""
    settings = get_settings()
    return redis_asyncio.from_url(settings.redis_url, decode_responses=True)  # type: ignore[no-any-return,no-untyped-call]
