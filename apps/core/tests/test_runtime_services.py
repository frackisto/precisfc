"""Cache, Celery et journalisation dans la configuration cPanel."""

import importlib

import pytest
from django.conf import settings
from django.core.cache import cache

from apps.core.tasks import ping


def test_celery_runs_tasks_synchronously_without_broker():
    assert settings.CELERY_TASK_ALWAYS_EAGER is True
    assert ping.delay().get(timeout=5) == "pong"


@pytest.mark.django_db
def test_database_cache_round_trip():
    assert settings.CACHES["default"]["BACKEND"] == "django.core.cache.backends.db.DatabaseCache"

    cache.set("precisfc:test", {"club": "Precis FC"}, 30)

    assert cache.get("precisfc:test") == {"club": "Precis FC"}


def test_production_logs_to_files_outside_public_folders():
    prod = importlib.import_module("config.settings.prod")
    handlers = prod.LOGGING["handlers"]

    assert handlers["file"]["filename"].endswith("django.log")
    assert handlers["errors_file"]["level"] == "ERROR"
    assert "mail_admins" in prod.LOGGING["loggers"]["django"]["handlers"]
