import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.accounts.roles import assign_role
from tests.factories import UserFactory


@pytest.fixture(autouse=True)
def setup_roles(db):
    call_command("setup_roles", verbosity=0)


@pytest.fixture
def make_user(db):
    """Utilisateur ayant les rôles donnés (``"superadmin"`` : superutilisateur)."""

    def make(*keys, **fields):
        if "superadmin" in keys:
            return User.objects.create_superuser(
                fields.pop("email", "super@precisfc.test"), "Mot-de-passe-test-2026", **fields
            )
        user = UserFactory(**fields)
        for key in keys:
            assign_role(user, key)
        return User.objects.get(pk=user.pk)

    return make


@pytest.fixture
def login(client, make_user):
    """Client connecté avec les rôles donnés."""

    def connect(*keys, **fields):
        user = make_user(*keys, **fields)
        client.force_login(user)
        client.user = user
        return client

    return connect
