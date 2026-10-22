"""Pages de classement : tableau, meilleurs buteurs et passeurs, graphique."""

import json
import re

import pytest
from django.urls import reverse

from apps.competitions.models import Participation, PlayerSeasonStat
from apps.competitions.services.recompute import recompute_edition
from apps.core.utils import years_ago
from tests.factories import ClubFactory, CompetitionSeasonFactory, MatchFactory, PlayerFactory

pytestmark = pytest.mark.django_db


def html(response):
    return response.content.decode()


@pytest.fixture
def edition():
    edition = CompetitionSeasonFactory(season__is_current=True)
    precis, asec = ClubFactory(name="Precis FC", is_own_club=True), ClubFactory(name="ASEC Mimosas")
    for club in (precis, asec):
        Participation.objects.create(competition_season=edition, club=club)
    MatchFactory(
        competition_season=edition,
        home_club=precis,
        away_club=asec,
        status="FINISHED",
        home_score=3,
        away_score=1,
    )
    recompute_edition(edition.pk)
    return edition


def test_list_shows_editions_of_the_current_season(client, edition):
    page = html(client.get(reverse("competitions:list")))

    assert edition.get_absolute_url() in page and edition.competition.name in page


def test_standings_table(client, edition):
    page = html(client.get(edition.get_absolute_url()))

    first = page.index("Precis FC", page.index("standings-table"))
    second = page.index("ASEC Mimosas", page.index("standings-table"))
    assert first < second
    assert 'class="table-active fw-semibold"' in page  # notre club mis en valeur
    assert "+2" in page and 'class="badge form-V' in page
    assert "Meilleure attaque" in page


def test_leaders_and_chart_exclude_minors_without_consent(client, edition):
    adult = PlayerFactory(first_name="Yao", last_name="Buteur")
    minor = PlayerFactory(first_name="Enfant", last_name="Protégé", birth_date=years_ago(15))
    PlayerSeasonStat.objects.create(player=adult, competition_season=edition, goals=5, assists=2)
    PlayerSeasonStat.objects.create(player=minor, competition_season=edition, goals=9, assists=4)

    page = html(client.get(edition.get_absolute_url()))
    chart = json.loads(
        re.search(r'id="donnees-buteurs" type="application/json">(.*?)</script>', page).group(1)
    )

    assert "Yao Buteur" in page and "Protégé" not in page
    assert chart == {"labels": ["Yao Buteur"], "values": [5]}
    assert "chart.umd.min.js" in page


def test_unknown_edition_returns_404(client):
    response = client.get(reverse("competitions:detail", args=["inconnue", "2099-2100"]))

    assert response.status_code == 404


def test_standings_page_query_count_is_bounded(client, edition, django_assert_max_num_queries):
    for number in range(15):
        PlayerSeasonStat.objects.create(
            player=PlayerFactory(), competition_season=edition, goals=number + 1, assists=1
        )
    client.get(edition.get_absolute_url())

    with django_assert_max_num_queries(12):
        client.get(edition.get_absolute_url())


def test_sitemap_lists_teams_public_players_matches_and_standings(client, edition):
    adult = PlayerFactory(first_name="Visible")
    minor = PlayerFactory(first_name="Invisible", birth_date=years_ago(15))

    sitemap = html(client.get("/sitemap.xml"))

    assert adult.get_absolute_url() in sitemap and minor.get_absolute_url() not in sitemap
    assert edition.get_absolute_url() in sitemap
    assert "/matchs/" in sitemap and "/equipes/" in sitemap
