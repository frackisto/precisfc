"""Statistiques des joueurs calculées depuis les compositions et les événements."""

import pytest

from apps.competitions.models import PlayerSeasonStat
from apps.competitions.services.player_stats import compute_player_stats, update_player_stats
from apps.matches.models import LineupEntry, MatchEvent, Side
from tests.factories import CompetitionSeasonFactory, MatchFactory, PlayerFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def edition():
    return CompetitionSeasonFactory()


def finished_match(edition, home_score=2, away_score=0, **kwargs):
    return MatchFactory(
        competition_season=edition,
        status="FINISHED",
        home_score=home_score,
        away_score=away_score,
        **kwargs,
    )


def lineup(match, player, *, starter=True, side=Side.HOME):
    return LineupEntry.objects.create(match=match, side=side, player=player, is_starter=starter)


def event(match, kind, minute, player=None, *, side=Side.HOME, **kwargs):
    return MatchEvent.objects.create(
        match=match,
        side=side,
        minute=minute,
        kind=kind,
        player=player,
        player_name="" if player else "X",
        **kwargs,
    )


def test_minutes_appearances_and_starts(edition):
    match = finished_match(edition)
    starter, substitute, replaced, bench = (PlayerFactory() for _ in range(4))
    for player in (starter, replaced):
        lineup(match, player)
    for player in (substitute, bench):
        lineup(match, player, starter=False)
    event(match, "SUBSTITUTION", 60, substitute, player_out=replaced)

    stats = compute_player_stats(edition)

    assert (
        stats[starter.pk]["appearances"],
        stats[starter.pk]["starts"],
        stats[starter.pk]["minutes"],
    ) == (1, 1, 90)
    assert (
        stats[substitute.pk]["appearances"],
        stats[substitute.pk]["starts"],
        stats[substitute.pk]["minutes"],
    ) == (1, 0, 30)
    assert stats[replaced.pk]["minutes"] == 60
    assert bench.pk not in stats


def test_goals_assists_and_own_goals(edition):
    match = finished_match(edition, 3, 1)
    scorer, passer, unlucky = PlayerFactory(), PlayerFactory(), PlayerFactory()
    event(match, "GOAL", 10, scorer, assist_player=passer)
    event(match, "PENALTY_GOAL", 50, scorer)
    event(match, "OWN_GOAL", 70, unlucky)
    event(match, "MISSED_PENALTY", 80, passer)

    stats = compute_player_stats(edition)

    assert stats[scorer.pk]["goals"] == 2
    assert stats[passer.pk]["assists"] == 1 and stats[passer.pk]["goals"] == 0
    assert stats[unlucky.pk]["goals"] == 0


def test_cards_and_sending_off_end_playing_time(edition):
    match = finished_match(edition)
    booked, sent_off = PlayerFactory(), PlayerFactory()
    lineup(match, booked)
    lineup(match, sent_off)
    event(match, "YELLOW", 20, booked)
    event(match, "YELLOW", 30, sent_off)
    event(match, "SECOND_YELLOW", 75, sent_off)

    stats = compute_player_stats(edition)

    assert (stats[booked.pk]["yellow_cards"], stats[booked.pk]["red_cards"]) == (1, 0)
    assert (stats[sent_off.pk]["yellow_cards"], stats[sent_off.pk]["red_cards"]) == (2, 1)
    assert stats[sent_off.pk]["minutes"] == 75


def test_clean_sheet_for_a_goalkeeper_who_played_the_whole_match(edition):
    keeper, outfield, replaced_keeper = (
        PlayerFactory(position="GK"),
        PlayerFactory(position="DF"),
        PlayerFactory(position="GK"),
    )
    shutout = finished_match(edition, 1, 0)
    lineup(shutout, keeper)
    lineup(shutout, outfield)
    away_shutout = finished_match(edition, 0, 2)
    lineup(away_shutout, keeper, side=Side.AWAY)
    conceded = finished_match(edition, 1, 1)
    lineup(conceded, keeper)
    substituted = finished_match(edition, 1, 0)
    lineup(substituted, replaced_keeper)
    event(substituted, "SUBSTITUTION", 80, PlayerFactory(), player_out=replaced_keeper)

    stats = compute_player_stats(edition)

    assert stats[keeper.pk]["clean_sheets"] == 2
    assert stats[outfield.pk]["clean_sheets"] == 0
    assert stats[replaced_keeper.pk]["clean_sheets"] == 0


def test_unfinished_matches_are_ignored(edition):
    player = PlayerFactory()
    match = MatchFactory(competition_season=edition, status="SCHEDULED")
    lineup(match, player)

    assert compute_player_stats(edition) == {}


def test_update_saves_one_line_per_player(edition):
    match = finished_match(edition)
    player = PlayerFactory()
    lineup(match, player)
    event(match, "GOAL", 5, player)

    update_player_stats(edition)
    update_player_stats(edition)

    line = PlayerSeasonStat.objects.get()
    assert (line.player, line.goals, line.season) == (player, 1, edition.season)


def test_stats_update_automatically_when_an_event_is_saved(
    edition, django_capture_on_commit_callbacks
):
    match = finished_match(edition)
    player = PlayerFactory()

    with django_capture_on_commit_callbacks(execute=True):
        lineup(match, player)
        event(match, "GOAL", 12, player)

    assert PlayerSeasonStat.objects.get(player=player).goals == 1
