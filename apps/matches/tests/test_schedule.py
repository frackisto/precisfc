"""Historique des changements d'horaire (reports)."""

from datetime import timedelta

import pytest
from django.urls import reverse

from apps.matches.models import MatchScheduleChange
from tests.factories import MatchFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_moving_a_match_keeps_the_original_kickoff_and_logs_each_change():
    match = MatchFactory()
    original = match.kickoff_at

    match.kickoff_at = original + timedelta(days=2)
    match.schedule_change_reason = "Indisponibilité du stade"
    match.save()
    match.kickoff_at = original + timedelta(days=9)
    match.save()

    match.refresh_from_db()
    assert match.original_kickoff_at == original
    assert match.is_rescheduled
    changes = list(match.schedule_changes.order_by("created_at", "pk"))
    assert [change.reason for change in changes] == [
        "Indisponibilité du stade",
        "Changement d'horaire",
    ]
    assert changes[1].old_kickoff_at == original + timedelta(days=2)


def test_saving_without_moving_the_match_logs_nothing():
    match = MatchFactory()
    match.referee = "Arbitre central"
    match.save()

    assert not MatchScheduleChange.objects.exists()
    assert match.original_kickoff_at is None


def test_admin_records_who_moved_the_match_and_why(client):
    admin = UserFactory(is_superuser=True)
    client.force_login(admin)
    match = MatchFactory()
    new_kickoff = (match.kickoff_at + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "competition_season": match.competition_season_id,
        "home_club": match.home_club_id,
        "away_club": match.away_club_id,
        "kickoff_at_0": new_kickoff.split()[0],
        "kickoff_at_1": new_kickoff.split()[1],
        "status": "POSTPONED",
        "slug": match.slug,
        "is_published": "on",
        "schedule_change_reason": "Demande de la Ligue",
    }
    for prefix in ("lineup", "events", "team_stats", "schedule_changes"):
        data.update({f"{prefix}-TOTAL_FORMS": "0", f"{prefix}-INITIAL_FORMS": "0"})

    response = client.post(reverse("admin:matches_match_change", args=[match.pk]), data)

    assert response.status_code == 302, response.content.decode()[:2000]
    change = MatchScheduleChange.objects.get()
    assert (change.changed_by, change.reason) == (admin, "Demande de la Ligue")
