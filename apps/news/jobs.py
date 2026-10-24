from datetime import timedelta

from apps.core.scheduling import scheduled_job

from .services.workflow import publish_due_articles


@scheduled_job(every=timedelta(minutes=5))
def publish_scheduled_articles():
    """Range au statut « publié » les articles programmés dont l'heure est passée."""
    publish_due_articles()
