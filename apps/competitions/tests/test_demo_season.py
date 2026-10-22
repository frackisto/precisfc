"""Commande demo_season : saison fictive complète, sans toucher aux vraies données."""

import pytest
from django.core.management import CommandError, call_command
from django.urls import reverse

from apps.competitions.management.commands.demo_season import round_robin
from apps.competitions.models import Club, CompetitionSeason, PlayerSeasonStat, Season, Standing
from apps.matches.models import Match, MatchEvent
from apps.teams.models import Player

pytestmark = pytest.mark.django_db


@pytest.fixture
def debug(settings):
    settings.DEBUG = True


def test_round_robin_pairs_every_club_once():
    rounds = round_robin("ABCDEFGH")
    pairs = [frozenset(pair) for day in rounds for pair in day]

    assert len(rounds) == 7 and all(len(day) == 4 for day in rounds)
    assert len(pairs) == len(set(pairs)) == 28


def test_creates_a_consistent_season(debug):
    call_command("demo_season", verbosity=0)

    edition = CompetitionSeason.objects.get(season__slug="demo-saison")
    finished = Match.objects.filter(competition_season=edition, status="FINISHED")
    assert Match.objects.filter(competition_season=edition).count() == 28
    assert finished.count() == 20
    assert Standing.objects.filter(competition_season=edition).count() == 8
    assert PlayerSeasonStat.objects.filter(competition_season=edition).exists()
    for match in finished.own_club():
        own_side = "HOME" if match.home_club.is_own_club else "AWAY"
        own_score = match.home_score if own_side == "HOME" else match.away_score
        goals = match.events.filter(side=own_side, kind__in=["GOAL", "PENALTY_GOAL"]).count()
        assert goals == own_score


def test_demo_pages_hide_the_minor_without_consent(debug, client):
    call_command("demo_season", verbosity=0)
    edition = CompetitionSeason.objects.get(season__slug="demo-saison")
    hidden = Player.objects.get(last_name="Protégé")
    visible = Player.objects.get(last_name="Espoir")

    team_page = client.get(edition.team.get_absolute_url()).content.decode()
    standings_page = client.get(edition.get_absolute_url()).content.decode()

    assert "Espoir" in team_page and "Protégé" not in team_page
    assert "Protégé" not in standings_page
    assert client.get(hidden.get_absolute_url()).status_code == 404
    assert client.get(visible.get_absolute_url()).status_code == 200
    assert client.get(reverse("matches:list")).status_code == 200


def test_running_twice_does_not_duplicate(debug):
    call_command("demo_season", verbosity=0)
    call_command("demo_season", verbosity=0)

    assert Season.objects.filter(slug="demo-saison").count() == 1
    assert Match.objects.count() == 28
    assert Player.objects.count() == 20


def test_existing_own_club_is_reused_and_kept(debug):
    real = Club.objects.create(name="Precis FC", is_own_club=True)
    real_match_count = 0

    call_command("demo_season", verbosity=0)
    assert Match.objects.own_club().count() == 7
    call_command("demo_season", "--delete", verbosity=0)

    assert Club.objects.filter(pk=real.pk).exists()
    assert Match.objects.count() == real_match_count
    assert not Club.objects.filter(slug__startswith="demo-").exists()
    assert not MatchEvent.objects.exists() and not Player.objects.exists()


def test_refuses_to_run_outside_development(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError, match="développement"):
        call_command("demo_season", verbosity=0)
    assert not Season.objects.exists()
