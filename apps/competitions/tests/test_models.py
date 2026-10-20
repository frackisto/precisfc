"""Saisons, compétitions, participants et classements."""

from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.competitions.models import (
    Club,
    Competition,
    Participation,
    PlayerSeasonStat,
    Season,
    Standing,
)
from tests.factories import (
    ClubFactory,
    CompetitionFactory,
    CompetitionSeasonFactory,
    PlayerFactory,
    SeasonFactory,
)
from tests.helpers import rejected_by_database

pytestmark = pytest.mark.django_db


def test_only_one_current_season():
    old = SeasonFactory(is_current=True)
    new = SeasonFactory(is_current=True)

    old.refresh_from_db()
    assert old.is_current is False
    assert Season.current() == new


def test_season_must_end_after_it_starts():
    with rejected_by_database():
        Season.objects.create(
            name="2026-2027", start_date=date(2027, 6, 1), end_date=date(2026, 8, 1)
        )


def test_only_one_own_club():
    first = ClubFactory(is_own_club=True)
    ClubFactory(is_own_club=True)

    first.refresh_from_db()
    assert first.is_own_club is False
    assert Club.objects.filter(is_own_club=True).count() == 1


def test_competition_has_default_points_and_tiebreak_rules():
    competition = CompetitionFactory()

    competition.full_clean()
    assert (competition.points_win, competition.points_draw, competition.points_loss) == (3, 1, 0)
    assert competition.tiebreak_rules[0] == "goal_difference"


@pytest.mark.parametrize(
    ("rules", "message"),
    [
        (["goal_difference", "coin_toss"], "inconnu"),
        (["goals_for", "goals_for"], "une fois"),
        ("goal_difference", "liste"),
    ],
)
def test_invalid_tiebreak_rules_are_rejected(rules, message):
    competition = CompetitionFactory.build(tiebreak_rules=rules)

    with pytest.raises(ValidationError, match=message):
        competition.full_clean()


def test_a_win_must_be_worth_more_than_a_draw():
    with rejected_by_database():
        Competition.objects.create(name="Coupe", kind="CUP", points_win=1, points_draw=1)


def test_team_is_engaged_once_per_edition():
    edition = CompetitionSeasonFactory()

    with rejected_by_database():
        CompetitionSeasonFactory(
            competition=edition.competition, season=edition.season, team=edition.team
        )


def test_points_adjustment_requires_a_reason():
    edition = CompetitionSeasonFactory()

    with rejected_by_database():
        Participation.objects.create(
            competition_season=edition, club=ClubFactory(), points_adjustment=-3
        )


def test_club_participates_once_per_edition():
    edition = CompetitionSeasonFactory()
    club = ClubFactory()
    Participation.objects.create(competition_season=edition, club=club)

    with rejected_by_database():
        Participation.objects.create(competition_season=edition, club=club)


def test_standing_played_matches_add_up():
    edition = CompetitionSeasonFactory()

    with rejected_by_database():
        Standing.objects.create(
            competition_season=edition, club=ClubFactory(), position=1, played=3, won=1
        )


def test_standing_points_can_be_negative_after_a_penalty():
    standing = Standing.objects.create(
        competition_season=CompetitionSeasonFactory(), club=ClubFactory(), position=16, points=-2
    )

    assert standing.points == -2


def test_player_stat_copies_the_season_of_its_edition():
    edition = CompetitionSeasonFactory()

    stat = PlayerSeasonStat.objects.create(
        player=PlayerFactory(), competition_season=edition, appearances=3, starts=2, goals=1
    )

    assert stat.season == edition.season


def test_player_cannot_start_more_matches_than_played():
    with rejected_by_database():
        PlayerSeasonStat.objects.create(
            player=PlayerFactory(),
            competition_season=CompetitionSeasonFactory(),
            appearances=1,
            starts=2,
        )
