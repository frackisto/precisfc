"""Profil et carnet d'adresses."""

import pytest

from apps.accounts.models import Address, Profile
from tests.factories import UserFactory
from tests.helpers import rejected_by_database

pytestmark = pytest.mark.django_db


def make_address(user, label, **kwargs):
    return Address.objects.create(
        user=user,
        label=label,
        full_name="Awa Traoré",
        phone="0701020304",
        line1="Rue des Jardins",
        **kwargs,
    )


def test_profile_defaults_to_ivory_coast():
    profile = Profile.objects.create(user=UserFactory())

    assert profile.country == "CI"
    assert profile.notify_news is True
    assert profile.notify_shop is False


def test_one_profile_per_user():
    user = UserFactory()
    Profile.objects.create(user=user)

    with rejected_by_database():
        Profile.objects.create(user=user)


def test_local_phone_number_is_stored_in_international_format():
    address = make_address(UserFactory(), "Maison")

    address.refresh_from_db()
    assert str(address.phone) == "+2250701020304"


def test_only_one_default_address_per_user():
    user = UserFactory()
    home = make_address(user, "Maison", is_default=True)
    office = make_address(user, "Bureau", is_default=True)

    home.refresh_from_db()
    assert office.is_default is True
    assert home.is_default is False


def test_default_address_of_another_user_is_untouched():
    other = make_address(UserFactory(), "Maison", is_default=True)
    make_address(UserFactory(), "Maison", is_default=True)

    other.refresh_from_db()
    assert other.is_default is True
