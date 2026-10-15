"""Tâches périodiques exécutées par le cron cPanel.

L'hébergement mutualisé n'autorise pas de processus permanent (Celery beat).
Une seule ligne cron appelle ``python manage.py run_scheduled_jobs`` toutes les
5 minutes ; chaque tâche déclarée ici décide si elle est due.

Déclarer une tâche dans le module ``jobs.py`` d'une application ::

    @scheduled_job(every=timedelta(minutes=15))
    def expire_pending_bookings():
        ...
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from django.db.models import Q
from django.utils import timezone
from django.utils.module_loading import autodiscover_modules

from .models import ScheduledJobRun

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = timedelta(minutes=30)


@dataclass(frozen=True)
class ScheduledJob:
    name: str
    func: Callable[[], object]
    every: timedelta
    timeout: timedelta


class Outcome(StrEnum):
    SUCCESS = "réussie"
    FAILED = "échouée"
    NOT_DUE = "pas encore due"
    LOCKED = "déjà en cours"


_registry: dict[str, ScheduledJob] = {}


def scheduled_job(*, every: timedelta, timeout: timedelta = DEFAULT_TIMEOUT, name: str = ""):
    def decorator(func):
        job_name = name or f"{func.__module__}.{func.__qualname__}"
        _registry[job_name] = ScheduledJob(job_name, func, every, timeout)
        return func

    return decorator


def get_jobs() -> list[ScheduledJob]:
    autodiscover_modules("jobs")
    return sorted(_registry.values(), key=lambda job: job.name)


def run_job(job: ScheduledJob, *, now=None, force: bool = False) -> Outcome:
    now = now or timezone.now()
    run, _ = ScheduledJobRun.objects.get_or_create(name=job.name)

    # Une tâche échouée est retentée au passage suivant du cron.
    succeeded_recently = (
        run.last_status == ScheduledJobRun.Status.SUCCESS
        and run.last_started_at is not None
        and now < run.last_started_at + job.every
    )
    if succeeded_recently and not force:
        return Outcome.NOT_DUE

    # Prise du verrou par un UPDATE conditionnel atomique : si deux cron se
    # chevauchent, un seul obtient la ligne.
    acquired = (
        ScheduledJobRun.objects.filter(pk=run.pk)
        .filter(Q(locked_until__isnull=True) | Q(locked_until__lte=now))
        .update(locked_until=now + job.timeout, last_started_at=now)
    )
    if not acquired:
        return Outcome.LOCKED

    try:
        job.func()
    except Exception as exc:
        logger.exception("La tâche planifiée %s a échoué", job.name)
        status, error, outcome = ScheduledJobRun.Status.FAILED, repr(exc)[:2000], Outcome.FAILED
    else:
        status, error, outcome = ScheduledJobRun.Status.SUCCESS, "", Outcome.SUCCESS

    ScheduledJobRun.objects.filter(pk=run.pk).update(
        locked_until=None,
        last_finished_at=timezone.now(),
        last_status=status,
        last_error=error,
    )
    return outcome
