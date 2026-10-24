"""Saisie rapide des scores : enregistrement, validation, portée de l'entraîneur,
recalcul du classement et historique."""

from datetime import timedelta

import pytest
from auditlog.models import LogEntry
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.competitions.models import Participation, Standing
from apps.matches.models import Match
from apps.teams.models import Staff
from tests.factories import ClubFactory, CompetitionSeasonFactory, MatchFactory

pytestmark = pytest.mark.django_db

SCORES = reverse("dashboard:scores")


def update_url(match):
    return reverse("dashboard:score_update", args=[match.pk])


@pytest.fixture
def past_match():
    edition = CompetitionSeasonFactory()
    home, away = ClubFactory(name="Precis FC", is_own_club=True), ClubFactory(name="AS Yopougon")
    for club in (home, away):
        Participation.objects.create(competition_season=edition, club=club)
    return MatchFactory(
        competition_season=edition,
        home_club=home,
        away_club=away,
        kickoff_at=timezone.now() - timedelta(hours=2),
    )


def test_page_lists_matches_to_score_and_recent_results(login, past_match):
    recent = MatchFactory(
        kickoff_at=timezone.now() - timedelta(days=2),
        status="FINISHED",
        home_score=1,
        away_score=1,
    )
    future = MatchFactory()

    response = login("sporting_director").get(SCORES)

    assert [row["match"] for row in response.context["awaiting"]] == [past_match]
    assert [row["match"] for row in response.context["recent"]] == [recent]
    page = response.content.decode()
    assert update_url(past_match) in page
    assert update_url(future) not in page


def test_saving_a_score_finishes_the_match_and_updates_the_standings(
    login, past_match, django_capture_on_commit_callbacks
):
    client = login("sporting_director")

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            update_url(past_match), {"home_score": 3, "away_score": 1, "status": "FINISHED"}
        )

    assert response.status_code == 302
    assert response["Location"] == SCORES
    past_match.refresh_from_db()
    assert (past_match.home_score, past_match.away_score) == (3, 1)
    assert past_match.status == Match.Status.FINISHED
    standing = Standing.objects.get(club=past_match.home_club)
    assert (standing.position, standing.points, standing.won) == (1, 3, 1)
    assert "Score enregistré" in client.get(SCORES).content.decode()


def test_score_change_is_recorded_with_its_author(login, past_match):
    client = login("sporting_director")

    client.post(update_url(past_match), {"home_score": 0, "away_score": 2, "status": "FINISHED"})

    entry = LogEntry.objects.get_for_object(past_match).latest("timestamp")
    assert entry.actor == client.user
    assert entry.changes_dict["away_score"] == ["None", "2"]


def test_live_score_keeps_the_match_open(login, past_match):
    login("sporting_director").post(
        update_url(past_match), {"home_score": 1, "away_score": 0, "status": "LIVE"}
    )

    past_match.refresh_from_db()
    assert past_match.status == Match.Status.LIVE
    assert past_match.home_score == 1


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"home_score": "", "away_score": "1", "status": "FINISHED"}, "obligatoire"),
        ({"home_score": "-1", "away_score": "1", "status": "FINISHED"}, "supérieure ou égale"),
        ({"home_score": "100", "away_score": "1", "status": "FINISHED"}, "Score invalide"),
        (
            {"home_score": 1, "away_score": 1, "home_penalties": 4, "status": "FINISHED"},
            "tirs au but des deux équipes",
        ),
        ({"home_score": 1, "away_score": 0, "status": "POSTPONED"}, "Sélectionnez un choix valide"),
    ],
)
def test_invalid_scores_are_refused(login, past_match, data, message):
    response = login("sporting_director").post(update_url(past_match), data)

    assert response.status_code == 400
    assert message in response.content.decode()
    past_match.refresh_from_db()
    assert past_match.status == Match.Status.SCHEDULED
    assert past_match.home_score is None


def test_penalty_shootout_is_saved(login, past_match):
    login("sporting_director").post(
        update_url(past_match),
        {
            "home_score": 1,
            "away_score": 1,
            "home_penalties": 5,
            "away_penalties": 4,
            "status": "FINISHED",
        },
    )

    past_match.refresh_from_db()
    assert (past_match.home_penalties, past_match.away_penalties) == (5, 4)


def test_coach_scores_only_his_team(login, past_match):
    client = login("coach")
    Staff.objects.create(
        first_name="Ali",
        last_name="Koné",
        role="HEAD_COACH",
        team=past_match.competition_season.team,
        user=client.user,
    )
    other = MatchFactory(kickoff_at=timezone.now() - timedelta(hours=1))

    page = client.get(SCORES)
    ok = client.post(
        update_url(past_match), {"home_score": 2, "away_score": 0, "status": "FINISHED"}
    )
    refused = client.post(
        update_url(other), {"home_score": 2, "away_score": 0, "status": "FINISHED"}
    )

    assert [row["match"] for row in page.context["awaiting"]] == [past_match]
    assert ok.status_code == 302
    assert refused.status_code == 404
    other.refresh_from_db()
    assert other.home_score is None


def test_coach_without_team_sees_nothing(login, past_match):
    client = login("coach")

    assert client.get(SCORES).context["awaiting"] == []
    response = client.post(update_url(past_match), {"home_score": 1, "away_score": 0})
    assert response.status_code == 404


def test_score_form_requires_the_csrf_token(make_user, past_match):
    client = Client(enforce_csrf_checks=True)
    client.force_login(make_user("sporting_director"))

    response = client.post(
        update_url(past_match), {"home_score": 1, "away_score": 0, "status": "FINISHED"}
    )

    assert response.status_code == 403
    past_match.refresh_from_db()
    assert past_match.home_score is None


def test_unknown_match_gives_404(login):
    response = login("superadmin").post(
        reverse("dashboard:score_update", args=[999999]), {"home_score": 1}
    )

    assert response.status_code == 404
