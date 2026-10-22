"""Calendrier, filtres, page de match et exports (.ics, PDF)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.utils import years_ago
from apps.matches.models import LineupEntry, MatchEvent
from tests.factories import (
    ClubFactory,
    CompetitionSeasonFactory,
    MatchFactory,
    PlayerFactory,
    SeasonFactory,
    TeamFactory,
)

pytestmark = pytest.mark.django_db


def html(response):
    return response.content.decode()


@pytest.fixture
def own_club():
    return ClubFactory(name="Precis FC", is_own_club=True)


def own_match(own_club, opponent="ASEC Mimosas", days=7, **kwargs):
    return MatchFactory(
        home_club=own_club,
        away_club=ClubFactory(name=opponent),
        kickoff_at=timezone.now() + timedelta(days=days),
        **kwargs,
    )


# --- Calendrier --------------------------------------------------------------------------


def test_calendar_lists_published_matches_of_our_club_only(client, own_club):
    own_match(own_club, "ASEC Mimosas")
    own_match(own_club, "Match masqué", is_published=False)
    MatchFactory(
        home_club=ClubFactory(name="Adversaire A"), away_club=ClubFactory(name="Adversaire B")
    )

    page = html(client.get(reverse("matches:list")))

    assert "ASEC Mimosas" in page
    assert "Match masqué" not in page and "Adversaire A" not in page


def test_calendar_filters_by_team_season_and_period(client, own_club):
    first_team, women = TeamFactory(name="Première"), TeamFactory(name="Féminines")
    season = SeasonFactory()
    own_match(
        own_club,
        "Contre les hommes",
        competition_season=CompetitionSeasonFactory(team=first_team, season=season),
    )
    own_match(
        own_club, "Contre les femmes", competition_season=CompetitionSeasonFactory(team=women)
    )
    own_match(
        own_club,
        "Match déjà joué",
        days=-3,
        status="FINISHED",
        home_score=2,
        away_score=1,
        competition_season=CompetitionSeasonFactory(team=first_team, season=season),
    )

    by_team = html(client.get(reverse("matches:list"), {"equipe": women.slug}))
    by_season = html(client.get(reverse("matches:list"), {"saison": season.slug}))
    results = html(client.get(reverse("matches:list"), {"periode": "resultats"}))
    upcoming = html(client.get(reverse("matches:list"), {"periode": "a-venir"}))

    assert "Contre les femmes" in by_team and "Contre les hommes" not in by_team
    assert "Contre les hommes" in by_season and "Contre les femmes" not in by_season
    assert (
        "Match déjà joué" in results and "2 – 1" in results and "Contre les hommes" not in results
    )
    assert "Match déjà joué" not in upcoming


def test_unknown_filter_value_does_not_crash(client, own_club):
    response = client.get(reverse("matches:list"), {"saison": "inconnue", "periode": "?"})

    assert response.status_code == 200


def test_calendar_is_paginated_and_keeps_filters(client, own_club):
    for day in range(25):
        own_match(own_club, f"Adversaire {day:02d}", days=day + 1)

    first = html(client.get(reverse("matches:list"), {"periode": "a-venir"}))
    second = html(client.get(reverse("matches:list"), {"periode": "a-venir", "page": 2}))

    assert "Page 1 sur 2" in first and "periode=a-venir&amp;page=2" in first
    assert "Adversaire 24" in second and "Adversaire 00" not in second


def test_calendar_query_count_is_bounded(client, own_club, django_assert_max_num_queries):
    for day in range(20):
        own_match(own_club, f"Adversaire {day}", days=day + 1)
    client.get(reverse("matches:list"))

    with django_assert_max_num_queries(12):
        client.get(reverse("matches:list"))


# --- Page de match -------------------------------------------------------------------------


def test_match_page_shows_score_events_and_lineups(client, own_club):
    match = own_match(own_club, days=-1, status="FINISHED", home_score=2, away_score=1)
    scorer = PlayerFactory(first_name="Yao", last_name="Buteur")
    LineupEntry.objects.create(
        match=match, side="HOME", player=scorer, shirt_number=9, is_captain=True
    )
    LineupEntry.objects.create(match=match, side="AWAY", player_name="Joueur Adverse")
    MatchEvent.objects.create(
        match=match, side="HOME", minute=90, added_time=2, kind="GOAL", player=scorer
    )

    page = html(client.get(match.get_absolute_url()))

    assert "2 – 1" in page
    assert "90+2’" in page and "Yao Buteur" in page
    assert "Joueur Adverse" in page
    assert '"@type": "SportsEvent"' in page


def test_match_page_hides_the_name_of_a_minor_without_consent(client, own_club):
    match = own_match(own_club, days=-1, status="FINISHED", home_score=1, away_score=0)
    minor = PlayerFactory(first_name="Enfant", last_name="Protégé", birth_date=years_ago(15))
    LineupEntry.objects.create(match=match, side="HOME", player=minor)
    MatchEvent.objects.create(match=match, side="HOME", minute=30, kind="GOAL", player=minor)

    page = html(client.get(match.get_absolute_url()))

    assert "Protégé" not in page
    assert "Joueur du club" in page
    assert minor.get_absolute_url() not in page


def test_postponed_match_shows_its_original_date(client, own_club):
    match = own_match(own_club)
    match.kickoff_at += timedelta(days=7)
    match.status = "POSTPONED"
    match.save()

    page = html(client.get(match.get_absolute_url()))

    assert "Reporté" in page and "Initialement prévu le" in page


def test_unpublished_match_returns_404(client, own_club):
    match = own_match(own_club, is_published=False)

    assert client.get(match.get_absolute_url()).status_code == 404


def test_home_match_card_links_to_the_match_page(client, own_club):
    match = own_match(own_club)

    assert match.get_absolute_url() in html(client.get("/"))


# --- Exports -------------------------------------------------------------------------------


def test_ics_export_is_a_valid_calendar(client, own_club):
    own_match(own_club, "Club, avec virgule; et point-virgule")
    own_match(own_club, "Match annulé", days=10, status="CANCELLED")

    response = client.get(reverse("matches:ics"))
    content = html(response)

    assert response["Content-Type"] == "text/calendar; charset=utf-8"
    assert content.startswith("BEGIN:VCALENDAR\r\n") and content.endswith("END:VCALENDAR\r\n")
    assert content.count("BEGIN:VEVENT") == 2
    assert "Club\\, avec virgule\\; et point-virgule" in content
    assert "STATUS:CANCELLED" in content
    assert all(len(line.encode()) <= 75 for line in content.split("\r\n"))


def test_ics_export_follows_the_filters(client, own_club):
    women = TeamFactory()
    own_match(
        own_club, "Contre les femmes", competition_season=CompetitionSeasonFactory(team=women)
    )
    own_match(own_club, "Autre équipe")

    content = html(client.get(reverse("matches:ics"), {"equipe": women.slug}))

    assert content.count("BEGIN:VEVENT") == 1 and "Contre les femmes" in content


def test_pdf_export(client, own_club):
    own_match(own_club, "Africa Sports")

    response = client.get(reverse("matches:pdf"))

    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert "calendrier-precis-fc.pdf" in response["Content-Disposition"]


def test_empty_pdf_export_still_works(client):
    assert client.get(reverse("matches:pdf")).content.startswith(b"%PDF")
