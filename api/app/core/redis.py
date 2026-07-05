from functools import lru_cache

import redis

from app.core.config import get_settings


@lru_cache
def get_redis_client() -> redis.Redis:
    settings = get_settings()
    # celery[redis]'s dependency pin forces an older `redis` package release
    # whose `from_url` loses its type info under mypy --strict; not our bug.
    return redis.from_url(settings.redis_url, decode_responses=True)  # type: ignore[no-any-return,no-untyped-call]
