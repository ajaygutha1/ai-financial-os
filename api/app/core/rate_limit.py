import logging
from collections.abc import Callable
from typing import cast

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.exceptions import TooManyRequestsError
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)


def _client_key(request: Request) -> str:
    # X-Forwarded-For first (set by a reverse proxy in front of the API in
    # any real deployment), falling back to the direct connection's address
    # for local/dev runs without one in front.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check(key: str, times: int, seconds: int) -> None:
    """Fixed-window counter: at most `times` increments of `key` per
    `seconds`. Redis being unreachable fails *open* -- logs a warning and
    lets the request through, same principle as EventBus.dispatch(): a
    Redis outage must not take the whole API down for legitimate users, and
    a rate limiter that fails closed turns an availability blip into a full
    outage."""
    try:
        client = get_redis_client()
        # redis-py's sync client methods are typed as a union that includes
        # Awaitable (shared typing with the async client) -- this call is
        # always the sync path, matching the same underlying gap documented
        # in core/redis.py's own ignore comment on from_url().
        count = cast(int, client.incr(key))
        if count == 1:
            client.expire(key, seconds)
    except Exception:
        logger.warning("Rate limiter unavailable (Redis error) -- failing open.", exc_info=True)
        return

    if count > times:
        raise TooManyRequestsError(
            f"Too many requests -- limit is {times} per {seconds}s for this action."
        )


def rate_limit(*, scope: str, times: int, seconds: int) -> Callable[[Request], None]:
    """A per-route FastAPI dependency version of _check, scoped separately
    from the global middleware below (so /login and /register don't share
    one budget, and don't share the much larger global ceiling either)."""

    def dependency(request: Request) -> None:
        _check(f"ratelimit:{scope}:{_client_key(request)}", times, seconds)

    return dependency


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """A coarse, defense-in-depth ceiling applied to every request regardless
    of route -- per-route limits (login, register, refresh) are far tighter
    and are what actually matters for brute-force protection; this just caps
    generic abuse/scraping against everything else. Runs the (blocking)
    Redis check in a threadpool since middleware.dispatch() executes
    directly on the event loop, unlike a sync route + dependency (which
    FastAPI already offloads to a threadpool on its own)."""

    def __init__(
        self,
        app: object,
        *,
        times: int = 300,
        seconds: int = 60,
        exempt_paths: set[str] | None = None,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._times = times
        self._seconds = seconds
        self._exempt_paths = exempt_paths or {"/health"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path not in self._exempt_paths:
            key = f"ratelimit:global:{_client_key(request)}"
            try:
                await run_in_threadpool(_check, key, self._times, self._seconds)
            except TooManyRequestsError as exc:
                # Unlike a route dependency, an exception raised here is
                # *outside* the app's registered AppError handler (that only
                # wraps the router, not middleware added via add_middleware),
                # so it has to be turned into a response by hand or it would
                # otherwise surface as an unhandled 500.
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
        response: Response = await call_next(request)
        return response
