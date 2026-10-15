from celery import shared_task


@shared_task
def ping():
    """Tâche de diagnostic : vérifie que Celery est opérationnel."""
    return "pong"
