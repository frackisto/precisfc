"""Tâches périodiques déclenchées par le cron cPanel."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.core import scheduling
from apps.core.models import ScheduledJobRun
from apps.core.scheduling import Outcome, ScheduledJob, run_job

pytestmark = pytest.mark.django_db

JOB_NAME = "tests.sample_job"


def make_job(func, every=timedelta(hours=1)):
    return ScheduledJob(JOB_NAME, func, every, timeout=timedelta(minutes=10))


def failing():
    raise RuntimeError("serveur SMTP injoignable")


def test_first_run_executes_and_records_success():
    calls = []

    assert run_job(make_job(lambda: calls.append(1))) is Outcome.SUCCESS

    run = ScheduledJobRun.objects.get(name=JOB_NAME)
    assert calls == [1]
    assert run.last_status == ScheduledJobRun.Status.SUCCESS
    assert run.last_finished_at is not None
    assert run.locked_until is None


def test_job_waits_for_its_interval():
    calls = []
    job = make_job(lambda: calls.append(1))
    now = timezone.now()

    run_job(job, now=now)

    assert run_job(job, now=now + timedelta(minutes=30)) is Outcome.NOT_DUE
    assert run_job(job, now=now + timedelta(hours=1, seconds=1)) is Outcome.SUCCESS
    assert len(calls) == 2


def test_failed_job_is_recorded_and_retried_next_tick():
    now = timezone.now()

    assert run_job(make_job(failing), now=now) is Outcome.FAILED
    run = ScheduledJobRun.objects.get(name=JOB_NAME)
    assert run.last_status == ScheduledJobRun.Status.FAILED
    assert "SMTP" in run.last_error
    assert run.locked_until is None

    calls = []
    assert run_job(make_job(lambda: calls.append(1)), now=now + timedelta(minutes=5)) is (
        Outcome.SUCCESS
    )
    assert calls == [1]


def test_locked_job_is_skipped_until_lock_expires():
    now = timezone.now()
    ScheduledJobRun.objects.create(name=JOB_NAME, locked_until=now + timedelta(minutes=5))
    calls = []
    job = make_job(lambda: calls.append(1))

    assert run_job(job, now=now) is Outcome.LOCKED
    assert calls == []
    # Un verrou expiré (processus tué par l'hébergeur) n'empêche pas la reprise.
    assert run_job(job, now=now + timedelta(minutes=6)) is Outcome.SUCCESS


def test_force_runs_a_job_that_is_not_due():
    calls = []
    job = make_job(lambda: calls.append(1))
    now = timezone.now()
    run_job(job, now=now)

    assert run_job(job, now=now + timedelta(minutes=1), force=True) is Outcome.SUCCESS
    assert len(calls) == 2


def test_command_lists_and_runs_declared_jobs():
    out = StringIO()
    call_command("run_scheduled_jobs", "--list", stdout=out)
    assert "apps.core.jobs.clear_expired_sessions" in out.getvalue()

    out = StringIO()
    call_command("run_scheduled_jobs", stdout=out)
    assert "clear_expired_sessions : réussie" in out.getvalue()

    out = StringIO()
    call_command("run_scheduled_jobs", stdout=out)
    assert "clear_expired_sessions : pas encore due" in out.getvalue()


def test_command_reports_failures(monkeypatch):
    monkeypatch.setitem(scheduling._registry, "tests.boom", make_job(failing))

    with pytest.raises(CommandError, match=JOB_NAME):
        call_command("run_scheduled_jobs", stdout=StringIO())


def test_command_rejects_unknown_job():
    with pytest.raises(CommandError, match="inconnue"):
        call_command("run_scheduled_jobs", "--job", "inexistante", stdout=StringIO())
