"""Matchs : cohérence du score, compositions, événements, statistiques."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from apps.matches.models import LineupEntry, MatchEvent, MatchTeamStat, Side
from tests.factories import ClubFactory, MatchFactory, PlayerFactory
from tests.helpers import rejected_by_database

pytestmark = pytest.mark.django_db


def test_match_slug_combines_clubs_and_local_date():
    match = MatchFactory(
        home_club=ClubFactory(name="Precis FC"),
        away_club=ClubFactory(name="ASEC Mimosas"),
        kickoff_at=datetime(2026, 11, 8, 23, 30, tzinfo=ZoneInfo("Africa/Abidjan")),
    )

    assert match.slug == "precis-fc-asec-mimosas-2026-11-08"


def test_a_club_cannot_play_against_itself():
    club = ClubFactory()

    with rejected_by_database():
        MatchFactory(home_club=club, away_club=club)


def test_finished_match_requires_a_score():
    with rejected_by_database():
        MatchFactory(status="FINISHED")


def test_finished_match_with_score_is_accepted():
    match = MatchFactory(status="FINISHED", home_score=2, away_score=0)

    assert match.pk is not None


def test_penalties_are_given_for_both_sides():
    with rejected_by_database():
        MatchFactory(status="FINISHED", home_score=1, away_score=1, home_penalties=4)


def test_lineup_entry_needs_a_player_or_a_name():
    match = MatchFactory()
    LineupEntry.objects.create(match=match, side=Side.AWAY, player_name="Joueur adverse")

    with rejected_by_database():
        LineupEntry.objects.create(match=match, side=Side.HOME)


def test_player_appears_once_in_a_lineup():
    match = MatchFactory()
    player = PlayerFactory()
    LineupEntry.objects.create(match=match, side=Side.HOME, player=player)

    with rejected_by_database():
        LineupEntry.objects.create(match=match, side=Side.HOME, player=player, is_starter=False)


def test_substitution_requires_the_outgoing_player():
    match = MatchFactory()

    with rejected_by_database():
        MatchEvent.objects.create(
            match=match, side=Side.HOME, minute=60, kind="SUBSTITUTION", player=PlayerFactory()
        )


def test_event_label_shows_added_time():
    event = MatchEvent.objects.create(
        match=MatchFactory(), side=Side.AWAY, minute=90, added_time=3, kind="GOAL", player_name="X"
    )

    assert str(event).startswith("90+3' But")


def test_shots_on_target_cannot_exceed_shots():
    with rejected_by_database():
        MatchTeamStat.objects.create(
            match=MatchFactory(), side=Side.HOME, shots=3, shots_on_target=5
        )


def test_one_statistics_line_per_side():
    match = MatchFactory()
    MatchTeamStat.objects.create(match=match, side=Side.HOME)

    with rejected_by_database():
        MatchTeamStat.objects.create(match=match, side=Side.HOME)


def test_possession_is_a_percentage():
    with rejected_by_database():
        MatchTeamStat.objects.create(match=MatchFactory(), side=Side.HOME, possession=120)
