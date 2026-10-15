from datetime import timedelta

from django.core.management import call_command

from .scheduling import scheduled_job


@scheduled_job(every=timedelta(days=1))
def clear_expired_sessions():
    """Supprime les sessions expirées de la base."""
    call_command("clearsessions")
