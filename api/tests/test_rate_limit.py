import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import AppError, TooManyRequestsError, app_error_handler
from app.core.rate_limit import GlobalRateLimitMiddleware, _check
from app.core.redis import get_redis_client


@pytest.fixture(autouse=True)
def _clean_rate_limit_keys() -> None:
    redis_client = get_redis_client()
    for key in redis_client.scan_iter("ratelimit:*"):
        redis_client.delete(key)


def test_check_allows_requests_within_the_limit() -> None:
    for _ in range(3):
        _check("ratelimit:test:within-limit", times=3, seconds=60)


def test_check_rejects_once_the_limit_is_exceeded() -> None:
    for _ in range(3):
        _check("ratelimit:test:over-limit", times=3, seconds=60)

    with pytest.raises(TooManyRequestsError):
        _check("ratelimit:test:over-limit", times=3, seconds=60)


def test_check_fails_open_when_redis_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise() -> None:
        raise ConnectionError("redis is down")

    monkeypatch.setattr("app.core.rate_limit.get_redis_client", _raise)

    # Must not raise even though Redis is unreachable -- a rate limiter
    # outage must not take down the whole API for legitimate users.
    _check("ratelimit:test:redis-down", times=1, seconds=60)
    _check("ratelimit:test:redis-down", times=1, seconds=60)


def _build_test_app(*, times: int, seconds: int) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)
    app.add_middleware(GlobalRateLimitMiddleware, times=times, seconds=seconds)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/widgets")
    def widgets() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_global_middleware_enforces_a_ceiling_across_all_routes() -> None:
    app = _build_test_app(times=2, seconds=60)
    with TestClient(app) as client:
        assert client.get("/widgets").status_code == 200
        assert client.get("/widgets").status_code == 200
        assert client.get("/widgets").status_code == 429


def test_global_middleware_exempts_the_health_check() -> None:
    app = _build_test_app(times=1, seconds=60)
    with TestClient(app) as client:
        # Health checks (used by container orchestration/load balancers) run
        # far more often than any real budget could accommodate.
        for _ in range(5):
            assert client.get("/health").status_code == 200
