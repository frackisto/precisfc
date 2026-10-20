"""Règles par objet : l'entraîneur et son équipe, le rédacteur et ses brouillons."""

import pytest
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.urls import reverse

from apps.accounts import roles
from apps.accounts.permissions import (
    can_change_article,
    can_change_match,
    can_change_player,
    can_confirm_manual_payment,
    can_download_application_document,
    can_publish_article,
    can_scan_tickets,
    require,
    team_scope,
)
from apps.accounts.roles import assign_role
from apps.news.models import Article
from apps.teams.models import Staff
from tests.factories import MatchFactory, PlayerFactory, TeamFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def setup_roles():
    call_command("setup_roles", verbosity=0)


def make_user(key):
    user = UserFactory()
    assign_role(user, key)
    user.refresh_from_db()
    return user


@pytest.fixture
def coach_setup():
    """Un entraîneur rattaché à son équipe, et une autre équipe du club."""
    coach = make_user(roles.COACH)
    own_team, other_team = TeamFactory(), TeamFactory()
    Staff.objects.create(
        first_name="Didier",
        last_name="Coach",
        role=Staff.Role.HEAD_COACH,
        team=own_team,
        user=coach,
    )
    return coach, own_team, other_team


def test_coach_manages_only_players_of_own_team(coach_setup):
    coach, own_team, other_team = coach_setup

    assert team_scope(coach) == {own_team.pk}
    assert can_change_player(coach, PlayerFactory(team=own_team))
    assert not can_change_player(coach, PlayerFactory(team=other_team))


def test_head_coach_of_a_team_without_staff_team_is_in_scope():
    coach = make_user(roles.COACH)
    staff = Staff.objects.create(first_name="A", last_name="B", role="HEAD_COACH", user=coach)
    team = TeamFactory(head_coach=staff)

    assert team_scope(coach) == {team.pk}


def test_coach_manages_only_matches_of_own_team(coach_setup):
    coach, own_team, other_team = coach_setup

    assert can_change_match(coach, MatchFactory(competition_season__team=own_team))
    assert not can_change_match(coach, MatchFactory(competition_season__team=other_team))


def test_sporting_director_manages_every_team(coach_setup):
    _, _, other_team = coach_setup
    director = make_user(roles.SPORTING_DIRECTOR)

    assert team_scope(director) is None
    assert can_change_match(director, MatchFactory(competition_season__team=other_team))


def test_coach_cannot_save_another_teams_match_in_admin(client, coach_setup):
    coach, own_team, other_team = coach_setup
    own_match = MatchFactory(competition_season__team=own_team)
    other_match = MatchFactory(competition_season__team=other_team)
    client.force_login(coach)

    own_page = client.get(reverse("admin:matches_match_change", args=[own_match.pk]))
    other_page = client.get(reverse("admin:matches_match_change", args=[other_match.pk]))
    other_post = client.post(reverse("admin:matches_match_change", args=[other_match.pk]), {})

    assert 'name="_save"' in own_page.content.decode()
    assert other_page.status_code == 200
    assert 'name="_save"' not in other_page.content.decode()
    assert other_post.status_code == 403


def test_coach_cannot_edit_another_teams_player_in_admin(client, coach_setup):
    coach, _, other_team = coach_setup
    client.force_login(coach)

    response = client.post(
        reverse("admin:teams_player_change", args=[PlayerFactory(team=other_team).pk]), {}
    )

    assert response.status_code == 403


def test_writer_edits_only_own_drafts():
    writer = make_user(roles.WRITER)
    own_draft = Article.objects.create(title="Mon brouillon", author=writer)
    own_in_review = Article.objects.create(
        title="En relecture", author=writer, status=Article.Status.IN_REVIEW
    )
    someone_else = Article.objects.create(title="Autre", author=UserFactory())

    assert can_change_article(writer, own_draft)
    assert not can_change_article(writer, own_in_review)
    assert not can_change_article(writer, someone_else)


def test_communication_manager_edits_any_article():
    manager = make_user(roles.COMMUNICATION)
    article = Article.objects.create(
        title="Communiqué", author=UserFactory(), status=Article.Status.IN_REVIEW
    )

    assert can_change_article(manager, article)


def test_writer_cannot_publish_from_the_admin(client):
    writer = make_user(roles.WRITER)
    client.force_login(writer)

    response = client.post(
        reverse("admin:news_article_add"),
        {"kind": "NEWS", "title": "Victoire", "status": "PUBLISHED", "is_featured": "on"},
    )

    article = Article.objects.get(title="Victoire")
    assert response.status_code == 302
    assert article.status == Article.Status.DRAFT
    assert article.is_featured is False
    assert article.author == writer


@pytest.mark.parametrize(
    ("check", "allowed_role", "denied_role"),
    [
        (can_confirm_manual_payment, roles.TREASURER, roles.SHOP_MANAGER),
        (can_scan_tickets, roles.TICKET_AGENT, roles.TREASURER),
        (can_download_application_document, roles.ACADEMY_MANAGER, roles.DIRECTION),
        (can_publish_article, roles.COMMUNICATION, roles.WRITER),
    ],
)
def test_business_actions_are_reserved_to_their_role(check, allowed_role, denied_role):
    assert check(make_user(allowed_role)) is True
    assert check(make_user(denied_role)) is False
    assert check(UserFactory()) is False


def test_user_without_article_permission_cannot_edit_even_own_article():
    supporter = UserFactory()

    assert not can_change_article(supporter, Article.objects.create(title="X", author=supporter))


def test_require_raises_403_when_refused():
    require(True)
    with pytest.raises(PermissionDenied):
        require(False)
