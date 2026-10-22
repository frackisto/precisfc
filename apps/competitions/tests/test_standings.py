"""Classements : barème, ajustements, critères de départage, groupes, recalcul automatique."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.competitions.models import Participation, Standing
from apps.competitions.services.standings import compute_standings, update_standings
from tests.factories import ClubFactory, CompetitionSeasonFactory, MatchFactory

pytestmark = pytest.mark.django_db


class League:
    """Petit championnat de test : clubs nommés et résultats saisis en une ligne."""

    def __init__(self, *names, rules=None, groups=None, **competition):
        self.edition = CompetitionSeasonFactory(
            **{f"competition__{k}": v for k, v in competition.items()}
        )
        if rules is not None:
            self.edition.competition.tiebreak_rules = rules
            self.edition.competition.save()
        self.clubs = {}
        for name in names:
            club = ClubFactory(name=name)
            self.clubs[name] = club
            Participation.objects.create(
                competition_season=self.edition, club=club, group_name=(groups or {}).get(name, "")
            )
        self.day = 0

    def play(self, home, home_score, away_score, away, status="FINISHED"):
        self.day += 1
        return MatchFactory(
            competition_season=self.edition,
            home_club=self.clubs[home],
            away_club=self.clubs[away],
            kickoff_at=timezone.now() - timedelta(days=100 - self.day),
            status=status,
            home_score=home_score if status == "FINISHED" else None,
            away_score=away_score if status == "FINISHED" else None,
        )

    def table(self):
        return [(position, row.club_name) for position, row in compute_standings(self.edition)]

    def row(self, name):
        return next(row for _, row in compute_standings(self.edition) if row.club_name == name)


def test_basic_table_counts_points_goals_and_form():
    league = League("ASEC", "Africa", "Precis")
    league.play("Precis", 2, 0, "ASEC")
    league.play("ASEC", 1, 1, "Africa")
    league.play("Africa", 0, 3, "Precis")

    precis = league.row("Precis")
    # ASEC et Africa : 1 point chacun ; différence de buts −2 contre −3.
    assert league.table() == [(1, "Precis"), (2, "ASEC"), (3, "Africa")]
    assert (precis.played, precis.won, precis.drawn, precis.lost) == (2, 2, 0, 0)
    assert (precis.goals_for, precis.goals_against, precis.goal_difference) == (5, 0, 5)
    assert precis.points == 6
    assert league.row("ASEC").form == "DN"


def test_points_scale_comes_from_the_competition():
    league = League("A", "B", points_win=2, points_draw=1)
    league.play("A", 1, 0, "B")

    assert league.row("A").points == 2


def test_points_adjustment_is_applied():
    league = League("A", "B")
    league.play("A", 1, 0, "B")
    Participation.objects.filter(club=league.clubs["A"]).update(
        points_adjustment=-6, adjustment_reason="Pénalité disciplinaire"
    )

    assert league.row("A").points == -3
    assert league.table() == [(1, "B"), (2, "A")]


def test_goal_difference_breaks_a_tie():
    league = League("A", "B", "C", rules=["goal_difference", "goals_for"])
    league.play("A", 3, 0, "C")
    league.play("B", 1, 0, "C")

    assert league.table() == [(1, "A"), (2, "B"), (3, "C")]


def test_goals_scored_break_a_tie_on_goal_difference():
    league = League("A", "B", "C", rules=["goal_difference", "goals_for"])
    league.play("A", 3, 2, "C")
    league.play("B", 1, 0, "C")

    assert league.table()[:2] == [(1, "A"), (2, "B")]


def two_club_tie(rules):
    """A et B à 3 points ; A a la meilleure différence de buts, B a gagné leur match."""
    league = League("A", "B", "C", "D", rules=rules)
    league.play("B", 1, 0, "A")
    league.play("A", 5, 0, "C")
    league.play("B", 0, 1, "D")
    league.play("D", 0, 0, "C")
    assert league.row("A").points == league.row("B").points == 3
    assert league.row("A").goal_difference > league.row("B").goal_difference
    return league


def test_head_to_head_can_come_before_goal_difference():
    league = two_club_tie(["head_to_head_points", "goal_difference"])

    assert league.table() == [(1, "D"), (2, "B"), (3, "A"), (4, "C")]


def test_same_tie_follows_goal_difference_when_rules_say_so():
    league = two_club_tie(["goal_difference", "head_to_head_points"])

    assert league.table() == [(1, "D"), (2, "A"), (3, "B"), (4, "C")]


def test_three_way_tie_uses_a_mini_league_between_tied_clubs_only():
    rules = ["head_to_head_points", "head_to_head_goal_difference", "goal_difference"]
    league = League("A", "B", "C", "D", rules=rules)
    # A, B et C se battent en cercle : égalité de points entre eux.
    league.play("A", 1, 0, "B")
    league.play("B", 3, 0, "C")
    league.play("C", 2, 1, "A")
    # Contre D, A gagne largement : cela ne doit pas compter dans le départage direct.
    league.play("A", 6, 0, "D")
    league.play("B", 1, 0, "D")
    league.play("C", 1, 0, "D")

    # Entre eux : B +2 (3-0, 0-1), C -2 (2-1, 0-3), A 0 (1-0, 1-2).
    assert league.table() == [(1, "B"), (2, "A"), (3, "C"), (4, "D")]


def test_wins_criterion():
    league = League("A", "B", "C", rules=["wins"], points_win=3, points_draw=1)
    league.play("A", 1, 0, "C")  # A : 1 victoire = 3 points
    league.play("B", 0, 0, "C")
    league.play("B", 1, 1, "C")
    league.play("B", 2, 2, "C")  # B : 3 nuls = 3 points

    assert league.table()[:2] == [(1, "A"), (2, "B")]


def test_away_goals_criterion():
    league = League("A", "B", "C", rules=["away_goals_for"])
    league.play("C", 2, 3, "A")  # A marque 3 buts à l'extérieur
    league.play("B", 3, 2, "C")  # B marque à domicile

    assert league.table()[:2] == [(1, "A"), (2, "B")]


def test_complete_tie_falls_back_to_alphabetical_order():
    league = League("Zébus FC", "Abeilles FC", rules=["goal_difference"])
    league.play("Zébus FC", 1, 1, "Abeilles FC")

    assert league.table() == [(1, "Abeilles FC"), (2, "Zébus FC")]


def test_only_finished_matches_between_participants_count():
    league = League("A", "B")
    league.play("A", 0, 0, "B", status="SCHEDULED")
    league.play("A", 0, 0, "B", status="POSTPONED")
    MatchFactory(
        competition_season=league.edition,
        home_club=league.clubs["A"],
        away_club=ClubFactory(name="Pas inscrit"),
        status="FINISHED",
        home_score=9,
        away_score=0,
    )

    assert league.row("A").played == 0
    assert [name for _, name in league.table()] == ["A", "B"]


def test_groups_are_ranked_separately():
    groups = {"A1": "A", "A2": "A", "B1": "B", "B2": "B"}
    league = League("A1", "A2", "B1", "B2", groups=groups)
    league.play("A2", 1, 0, "A1")
    league.play("B1", 2, 0, "B2")
    league.play("A1", 5, 0, "B1")  # entre groupes : ignoré

    table = [
        (row.group, position, row.club_name) for position, row in compute_standings(league.edition)
    ]
    assert table == [("A", 1, "A2"), ("A", 2, "A1"), ("B", 1, "B1"), ("B", 2, "B2")]


def test_update_standings_saves_rows_and_is_idempotent():
    league = League("A", "B")
    league.play("A", 2, 1, "B")

    update_standings(league.edition)
    update_standings(league.edition)

    rows = list(Standing.objects.filter(competition_season=league.edition).order_by("position"))
    assert [(row.club.name, row.points, row.form) for row in rows] == [("A", 3, "V"), ("B", 0, "D")]


def test_cups_have_no_standings():
    league = League("A", "B", has_standings=False)
    league.play("A", 2, 1, "B")

    assert update_standings(league.edition) == 0
    assert not Standing.objects.exists()


def test_standings_update_automatically_when_a_score_is_saved(django_capture_on_commit_callbacks):
    league = League("A", "B")
    with django_capture_on_commit_callbacks(execute=True):
        match = league.play("A", 0, 0, "B", status="SCHEDULED")
    assert Standing.objects.get(club=league.clubs["A"]).points == 0

    with django_capture_on_commit_callbacks(execute=True):
        match.status, match.home_score, match.away_score = "FINISHED", 2, 0
        match.save()

    assert Standing.objects.get(club=league.clubs["A"]).points == 3


def test_changing_the_points_scale_recomputes_existing_standings(
    django_capture_on_commit_callbacks,
):
    league = League("A", "B")
    with django_capture_on_commit_callbacks(execute=True):
        league.play("A", 1, 0, "B")

    with django_capture_on_commit_callbacks(execute=True):
        competition = league.edition.competition
        competition.points_win = 2
        competition.save()

    assert Standing.objects.get(club=league.clubs["A"]).points == 2


def test_recompute_command_rebuilds_every_edition():
    league = League("A", "B")
    league.play("A", 1, 0, "B")  # sans recalcul automatique (pas de validation de transaction)
    assert not Standing.objects.exists()

    call_command("recompute_standings", verbosity=0)

    assert Standing.objects.get(club=league.clubs["A"]).points == 3
