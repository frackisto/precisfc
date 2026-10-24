"""Les 13 rôles : création des groupes, droits accordés et refusés, accès à l'administration."""

import pytest
from django.contrib.auth.models import Group, Permission
from django.core.management import CommandError, call_command
from django.urls import reverse

from apps.accounts import roles
from apps.accounts.roles import ROLES, assign_role, has_role
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def setup_roles():
    call_command("setup_roles", verbosity=0)


def user_with(*keys):
    user = UserFactory()
    for key in keys:
        assign_role(user, key)
    user.refresh_from_db()
    return user


def test_thirteen_roles_are_defined():
    assert len(ROLES) + 1 == 13  # + super administrateur (superutilisateur Django)
    assert Group.objects.filter(name__in=[role.name for role in ROLES.values()]).count() == 12


def test_setup_roles_is_idempotent_and_removes_stray_permissions():
    writer_group = Group.objects.get(name=ROLES[roles.WRITER].name)
    expected = set(writer_group.permissions.values_list("pk", flat=True))
    writer_group.permissions.add(Permission.objects.get(codename="confirm_manual_payment"))

    call_command("setup_roles", verbosity=0)
    call_command("setup_roles", verbosity=0)

    assert set(writer_group.permissions.values_list("pk", flat=True)) == expected
    assert Group.objects.filter(name=ROLES[roles.WRITER].name).count() == 1


def test_setup_roles_rejects_unknown_permissions(monkeypatch):
    broken = roles.Role("x", "Rôle cassé", "", frozenset({"news.fly_article"}))
    monkeypatch.setitem(ROLES, "x", broken)

    with pytest.raises(CommandError, match="news.fly_article"):
        call_command("setup_roles", verbosity=0)


# Pour chaque rôle : des droits qu'il doit avoir, et d'autres qu'il ne doit surtout pas avoir.
MATRIX = {
    roles.DIRECTION: (
        [
            "orders.view_order",
            "payments.view_payment",
            "core.view_financial_reports",
            "core.view_all_indicators",
        ],
        ["matches.change_match", "academy.view_application", "payments.confirm_manual_payment"],
    ),
    roles.CLUB_ADMIN: (
        ["core.change_page", "core.change_clubsettings", "news.publish_article"],
        ["payments.view_payment", "accounts.change_user", "academy.view_application"],
    ),
    roles.COMMUNICATION: (
        ["news.publish_article", "media_library.add_photo", "core.change_heroslide"],
        ["matches.change_match", "orders.view_order", "accounts.view_user"],
    ),
    roles.WRITER: (
        ["news.add_article", "news.change_article", "news.add_tag"],
        ["news.publish_article", "news.delete_article", "media_library.change_photo"],
    ),
    roles.MEDIA_MANAGER: (
        ["media_library.add_album", "media_library.delete_video"],
        ["news.change_article", "teams.change_player"],
    ),
    roles.SPORTING_DIRECTOR: (
        ["teams.change_team", "matches.add_match", "competitions.change_participation"],
        ["news.change_article", "orders.view_order", "competitions.change_standing"],
    ),
    roles.COACH: (
        ["matches.add_matchevent", "matches.change_lineupentry", "teams.change_player"],
        ["teams.add_player", "teams.change_team", "matches.delete_match"],
    ),
    roles.SHOP_MANAGER: (
        ["shop.change_product", "orders.change_order", "shop.add_stockmovement"],
        ["orders.delete_order", "shop.change_stockmovement", "payments.confirm_manual_payment"],
    ),
    roles.TREASURER: (
        ["payments.confirm_manual_payment", "core.view_financial_reports", "orders.view_order"],
        [
            "payments.change_payment",
            "orders.change_order",
            "shop.change_product",
            "core.view_all_indicators",
        ],
    ),
    roles.TICKETING_MANAGER: (
        ["ticketing.add_ticketcategory", "ticketing.scan_ticket", "ticketing.view_booking"],
        ["payments.confirm_manual_payment", "ticketing.delete_booking"],
    ),
    roles.TICKET_AGENT: (
        ["ticketing.scan_ticket"],
        ["core.view_dashboard", "ticketing.view_booking", "matches.view_match"],
    ),
    roles.ACADEMY_MANAGER: (
        ["academy.download_private_document", "academy.change_application"],
        ["academy.delete_application", "payments.view_payment", "teams.change_player"],
    ),
}


@pytest.mark.parametrize("key", list(MATRIX), ids=lambda key: ROLES[key].name)
def test_role_grants_and_denies_the_right_permissions(key):
    allowed, denied = MATRIX[key]
    user = user_with(key)

    assert all(user.has_perm(perm) for perm in allowed), allowed
    assert not any(user.has_perm(perm) for perm in denied), denied


def test_every_role_is_covered_by_the_matrix():
    assert set(MATRIX) == set(ROLES)


def test_supporter_has_no_internal_permission():
    supporter = UserFactory()

    assert supporter.get_all_permissions() == set()
    assert supporter.is_staff is False


def test_superadmin_has_every_permission():
    admin = UserFactory(is_superuser=True)

    assert has_role(admin, roles.SUPERADMIN)
    assert admin.has_perm("payments.confirm_manual_payment")
    assert admin.is_staff is True


def test_roles_can_be_combined():
    user = user_with(roles.WRITER, roles.MEDIA_MANAGER)

    assert has_role(user, roles.WRITER) and has_role(user, roles.MEDIA_MANAGER)
    assert user.has_perm("news.add_article") and user.has_perm("media_library.add_album")


@pytest.mark.parametrize("key", [key for key in ROLES if key != roles.TICKET_AGENT])
def test_internal_roles_give_access_to_the_admin(key, client):
    user = user_with(key)
    client.force_login(user)

    assert user.is_staff is True
    assert client.get(reverse("admin:index")).status_code == 200


def test_ticket_agent_and_supporter_cannot_open_the_admin(client):
    for user in (user_with(roles.TICKET_AGENT), UserFactory()):
        client.force_login(user)

        assert user.is_staff is False
        assert client.get(reverse("admin:index")).status_code == 302


def test_admin_access_follows_role_removal():
    user = user_with(roles.SHOP_MANAGER)
    user.groups.clear()
    user.refresh_from_db()

    assert user.is_staff is False


def test_admin_access_follows_roles_added_from_the_group_side():
    user = UserFactory()
    Group.objects.get(name=ROLES[roles.TREASURER].name).user_set.add(user)
    user.refresh_from_db()

    assert user.is_staff is True


def test_staff_flag_cannot_be_forced_without_a_role():
    user = UserFactory(is_staff=True)
    user.refresh_from_db()

    assert user.is_staff is False


def test_direction_cannot_see_children_applications_but_academy_manager_can(client):
    url = reverse("admin:academy_application_changelist")

    client.force_login(user_with(roles.DIRECTION))
    assert client.get(url).status_code == 403

    client.force_login(user_with(roles.ACADEMY_MANAGER))
    assert client.get(url).status_code == 200


def test_direction_views_orders_without_being_able_to_change_them(client):
    client.force_login(user_with(roles.DIRECTION))

    assert client.get(reverse("admin:orders_order_changelist")).status_code == 200
    assert client.get(reverse("admin:teams_team_add")).status_code == 403
