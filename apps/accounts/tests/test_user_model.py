import pytest
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.accounts.models import User

pytestmark = pytest.mark.django_db

PASSWORD = "Un-mot-de-passe-solide-2026"


def test_custom_user_model_is_active():
    assert get_user_model() is User
    assert User.USERNAME_FIELD == "email"


def test_create_user_normalizes_email_and_hashes_password():
    user = User.objects.create_user("  Supporter@Precis.CI ", password=PASSWORD)

    assert user.email == "supporter@precis.ci"
    assert user.check_password(PASSWORD)
    assert PASSWORD not in user.password
    assert user.is_staff is False
    assert user.is_superuser is False


def test_email_is_required():
    with pytest.raises(ValueError, match="obligatoire"):
        User.objects.create_user("", password=PASSWORD)


def test_email_uniqueness_is_case_insensitive():
    User.objects.create_user("joueur@precis.ci")

    # Même en contournant la normalisation, la collation _ci de MariaDB refuse le doublon.
    with pytest.raises(IntegrityError), transaction.atomic():
        User(email="JOUEUR@PRECIS.CI").save()


def test_login_with_differently_cased_email(rf):
    user = User.objects.create_user("staff@precis.ci", password=PASSWORD)

    # django-axes exige la requête à chaque tentative (comptage des échecs par IP).
    assert authenticate(rf.post("/"), username="Staff@Precis.CI", password=PASSWORD) == user


def test_create_superuser_sets_flags():
    admin = User.objects.create_superuser("admin@precis.ci", password=PASSWORD)

    assert admin.is_staff is True
    assert admin.is_superuser is True


def test_create_superuser_refuses_inconsistent_flags():
    with pytest.raises(ValueError, match="is_staff"):
        User.objects.create_superuser("x@precis.ci", password=PASSWORD, is_staff=False)


def test_str_prefers_full_name_then_email():
    user = User.objects.create_user("kouame@precis.ci", first_name="Kouamé", last_name="Yao")
    anonymous = User.objects.create_user("sans.nom@precis.ci")

    assert str(user) == "Kouamé Yao"
    assert str(anonymous) == "sans.nom@precis.ci"


def test_admin_can_list_and_create_users(admin_client):
    assert admin_client.get(reverse("admin:accounts_user_changelist")).status_code == 200
    assert admin_client.get(reverse("admin:accounts_user_add")).status_code == 200

    response = admin_client.post(
        reverse("admin:accounts_user_add"),
        {
            "email": "Nouveau@Precis.ci",
            "usable_password": "true",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )

    assert response.status_code == 302
    assert User.objects.filter(email="nouveau@precis.ci").exists()
