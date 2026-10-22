"""Pages publiques des équipes et des joueurs, avec la règle de confidentialité des mineurs."""

import pytest
from django.urls import reverse

from apps.competitions.models import PlayerSeasonStat
from apps.core.utils import years_ago
from apps.teams.models import Staff
from tests.factories import CompetitionSeasonFactory, PlayerFactory, TeamFactory

pytestmark = pytest.mark.django_db


def html(response):
    return response.content.decode()


def test_team_list_shows_published_teams_only(client):
    TeamFactory(name="Équipe première")
    TeamFactory(name="Équipe cachée", is_published=False)

    page = html(client.get(reverse("teams:list")))

    assert "Équipe première" in page and "Équipe cachée" not in page


def test_menu_now_lists_teams_and_matches(client):
    page = html(client.get("/"))

    assert 'href="/equipes/"' in page and 'href="/matchs/"' in page


def test_squad_never_shows_a_minor_without_consent(client):
    team = TeamFactory()
    PlayerFactory(team=team, first_name="Adulte", position="GK")
    PlayerFactory(
        team=team,
        first_name="Mineur",
        last_name="Consentant",
        birth_date=years_ago(16),
        publication_consent=True,
    )
    PlayerFactory(team=team, first_name="Mineur", last_name="Protégé", birth_date=years_ago(16))
    PlayerFactory(team=team, first_name="Fiche", last_name="Masquée", is_published=False)

    page = html(client.get(team.get_absolute_url()))

    assert "Adulte" in page and "Gardiens" in page
    assert "Consentant" in page
    assert "Protégé" not in page and "Masquée" not in page


def test_team_page_shows_published_staff(client):
    team = TeamFactory()
    Staff.objects.create(team=team, first_name="Didier", last_name="Coach", role="HEAD_COACH")
    Staff.objects.create(
        team=team, first_name="Staff", last_name="Caché", role="ANALYST", is_published=False
    )

    page = html(client.get(team.get_absolute_url()))

    assert "Didier Coach" in page and "Entraîneur principal" in page
    assert "Caché" not in page


def test_unpublished_team_returns_404(client):
    team = TeamFactory(is_published=False)

    assert client.get(team.get_absolute_url()).status_code == 404


def test_minor_without_consent_has_no_public_page_even_by_direct_link(client):
    minor = PlayerFactory(birth_date=years_ago(15))

    assert client.get(minor.get_absolute_url()).status_code == 404


def test_minor_with_consent_shows_birth_year_only_and_no_physical_data(client):
    birth_date = years_ago(16)
    minor = PlayerFactory(
        birth_date=birth_date, publication_consent=True, height_cm=170, weight_kg=60
    )

    page = html(client.get(minor.get_absolute_url()))

    assert "Année de naissance" in page and str(birth_date.year) in page
    assert birth_date.strftime("%d/%m/%Y") not in page
    assert "170 cm" not in page and "60 kg" not in page


def test_adult_player_page_with_stats(client):
    player = PlayerFactory(height_cm=182, show_physical=True, bio="Milieu créatif.")
    PlayerSeasonStat.objects.create(
        player=player,
        competition_season=CompetitionSeasonFactory(),
        appearances=10,
        starts=8,
        goals=4,
    )

    page = html(client.get(player.get_absolute_url()))

    assert player.full_name in page and "182 cm" in page and "Milieu créatif." in page
    assert '"@type": "Person"' in page
    assert '<td class="text-end fw-semibold">4</td>' in page
