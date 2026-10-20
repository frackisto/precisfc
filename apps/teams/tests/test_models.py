"""Équipes et joueurs : numéros, slugs et confidentialité des mineurs."""

from datetime import date

import pytest

from apps.core.utils import years_ago
from apps.teams.models import Player
from tests.factories import PlayerFactory, TeamFactory
from tests.helpers import rejected_by_database

pytestmark = pytest.mark.django_db


def minor_birth_date():
    return years_ago(15)


def test_player_slug_uses_full_name():
    player = PlayerFactory(first_name="Sébastien", last_name="Haller")

    assert player.slug == "sebastien-haller"


def test_shirt_number_is_unique_within_a_team():
    team = TeamFactory()
    PlayerFactory(team=team, shirt_number=10)

    with rejected_by_database():
        PlayerFactory(team=team, shirt_number=10)


def test_same_shirt_number_allowed_in_another_team_and_without_number():
    team = TeamFactory()
    PlayerFactory(team=team, shirt_number=10)
    PlayerFactory(team=TeamFactory(), shirt_number=10)
    PlayerFactory(team=team, shirt_number=None)
    PlayerFactory(team=team, shirt_number=None)

    assert Player.objects.filter(shirt_number=10).count() == 2


def test_team_with_players_cannot_be_deleted():
    player = PlayerFactory()

    with rejected_by_database():
        player.team.delete()


def test_minor_without_consent_is_hidden_from_public():
    minor = PlayerFactory(birth_date=minor_birth_date(), publication_consent=False)

    assert minor.is_minor is True
    assert minor not in Player.objects.public()


def test_minor_with_consent_is_public_with_birth_year_only():
    birth_date = minor_birth_date()
    minor = PlayerFactory(birth_date=birth_date, publication_consent=True, show_birth_date=True)

    assert minor in Player.objects.public()
    assert minor.public_birth_date_label == str(birth_date.year)


def test_adult_is_public_and_birth_date_follows_display_choice():
    adult = PlayerFactory(birth_date=date(1995, 1, 31), show_birth_date=False)

    assert adult in Player.objects.public()
    assert adult.public_birth_date_label == ""

    adult.show_birth_date = True
    assert adult.public_birth_date_label == "31/01/1995"


def test_player_turning_eighteen_today_is_an_adult():
    player = PlayerFactory(birth_date=years_ago(18), publication_consent=False)

    assert player.is_minor is False
    assert player in Player.objects.public()


def test_unpublished_player_is_never_public():
    player = PlayerFactory(is_published=False, publication_consent=True)

    assert player not in Player.objects.public()
