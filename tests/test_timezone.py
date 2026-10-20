"""Requêtes par date (listes de l'administration, tableaux de bord) sur MariaDB."""

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.matches.models import Match
from tests.factories import MatchFactory

pytestmark = pytest.mark.django_db


def test_dates_can_be_grouped_by_month_in_the_club_time_zone():
    match = MatchFactory()

    months = list(Match.objects.dates("kickoff_at", "month"))

    assert len(months) == 1
    assert months[0].month == match.kickoff_at.month


def test_admin_date_hierarchy_works_with_data(client):
    client.force_login(User.objects.create_superuser("direction@precisfc.test", "x-2026-Precis"))
    MatchFactory()

    response = client.get(reverse("admin:matches_match_changelist"))

    assert response.status_code == 200


def test_database_time_zone_is_the_club_zone_with_no_offset(settings):
    # Condition de validité du réglage DATABASES["default"]["TIME_ZONE"] (voir base.py) :
    # si le fuseau du club changeait pour un fuseau à décalage ou à heure d'été,
    # il faudrait revoir ce choix (les dates déjà stockées sont en UTC).
    from datetime import datetime
    from zoneinfo import ZoneInfo

    zone = ZoneInfo(settings.DATABASES["default"]["TIME_ZONE"])
    assert settings.DATABASES["default"]["TIME_ZONE"] == settings.TIME_ZONE == "Africa/Abidjan"
    for month in range(1, 13):
        assert datetime(2026, month, 15, tzinfo=zone).utcoffset().total_seconds() == 0


def test_stored_values_are_unchanged_utc():
    from datetime import UTC, datetime

    from django.db import connection

    match = MatchFactory(kickoff_at=datetime(2026, 11, 8, 18, 30, tzinfo=UTC))
    with connection.cursor() as cursor:
        cursor.execute("SELECT kickoff_at FROM matches_match WHERE id = %s", [match.pk])
        raw = cursor.fetchone()[0]

    assert raw.replace(tzinfo=None) == datetime(2026, 11, 8, 18, 30)
