from celery import shared_task


@shared_task
def ping() -> str:
    """Smallest possible task: proves the Celery worker is connected."""
    return "pong"
