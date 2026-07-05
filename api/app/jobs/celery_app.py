from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("finos", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "sync-all-active-accounts": {
        "task": "app.jobs.tasks.sync_accounts.sync_all_active_accounts",
        "schedule": 6 * 60 * 60,  # every 6 hours
    },
}

# autodiscover_tasks appends ".tasks" to each entry itself, so the argument
# is the *parent* package ("app.jobs" -> looks for "app.jobs.tasks") -- not
# "app.jobs.tasks" itself, which would look for a non-existent
# "app.jobs.tasks.tasks". Importing the tasks package only registers its
# submodules if __init__.py itself imports them (see app/jobs/tasks/__init__.py).
celery_app.autodiscover_tasks(["app.jobs"])
