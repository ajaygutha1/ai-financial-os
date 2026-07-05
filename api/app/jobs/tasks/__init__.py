from app.jobs.tasks import sync_accounts  # noqa: F401  (registers tasks with the Celery app)

__all__ = ["sync_accounts"]
