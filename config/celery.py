"""Application Celery.

Sur cPanel, les tâches s'exécutent de façon synchrone (CELERY_TASK_ALWAYS_EAGER).
Sur un VPS : ``celery -A config worker -l info`` (Windows : ajouter ``--pool=solo``).
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

app = Celery("precisfc")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
