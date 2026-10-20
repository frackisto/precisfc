"""Inscription, vérification de l'e-mail, verrouillage après échecs, espace « Mon compte »."""

import re

import pytest
from axes.models import AccessAttempt
from django.core import mail
from django.urls import reverse

from apps.accounts.models import Profile, User
from config.settings import base

pytestmark = pytest.mark.django_db

PASSWORD = "Allez-Precis-FC-2026"
WRONG = "mauvais-mot-de-passe"


def login(client, email, password, ip="10.0.0.1"):
    return client.post(
        reverse("account_login"), {"login": email, "password": password}, REMOTE_ADDR=ip
    )


@pytest.fixture
def verified_user():
    user = User.objects.create_user("awa@precisfc.test", password=PASSWORD)
    user.emailaddress_set.create(email=user.email, verified=True, primary=True)
    return user


def test_passwords_are_hashed_with_argon2_in_real_environments():
    assert base.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher")


def test_signup_creates_account_profile_and_sends_verification_email(client):
    response = client.post(
        reverse("account_signup"),
        {"email": "Supporter@Precisfc.test", "password1": PASSWORD, "password2": PASSWORD},
    )

    user = User.objects.get(email="supporter@precisfc.test")
    assert response.status_code == 302
    assert response["Location"] == reverse("account_email_verification_sent")
    assert Profile.objects.filter(user=user).exists()
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject.startswith("[Precis FC]")


def test_login_is_refused_until_email_is_verified(client):
    client.post(
        reverse("account_signup"),
        {"email": "kofi@precisfc.test", "password1": PASSWORD, "password2": PASSWORD},
    )
    client.logout()

    response = login(client, "kofi@precisfc.test", PASSWORD)

    assert response.status_code == 302
    assert response["Location"] == reverse("account_email_verification_sent")
    assert "_auth_user_id" not in client.session


def test_confirmation_link_verifies_email_and_logs_in(client):
    client.post(
        reverse("account_signup"),
        {"email": "ines@precisfc.test", "password1": PASSWORD, "password2": PASSWORD},
    )
    link = re.search(r"https?://\S+/compte/confirm-email/\S+/", mail.outbox[0].body).group(0)
    path = link.split("://", 1)[1].split("/", 1)[1]

    response = client.post(f"/{path}")

    assert response.status_code == 302
    assert User.objects.get(email="ines@precisfc.test").emailaddress_set.get().verified
    assert client.get(reverse("accounts:profile")).status_code == 200


def test_signup_can_be_closed(client, settings):
    settings.ACCOUNT_SIGNUP_OPEN = False

    response = client.post(
        reverse("account_signup"),
        {"email": "ferme@precisfc.test", "password1": PASSWORD, "password2": PASSWORD},
    )

    assert not User.objects.filter(email="ferme@precisfc.test").exists()
    assert "account/signup_closed.html" in [t.name for t in response.templates]


def test_verified_user_logs_in_and_lands_on_profile(client, verified_user):
    response = login(client, "AWA@precisfc.test", PASSWORD)

    assert response.status_code == 302
    assert response["Location"] == reverse("accounts:profile")


def test_account_is_locked_after_five_failures_even_with_the_right_password(client, verified_user):
    for _ in range(5):
        login(client, verified_user.email, WRONG)

    response = login(client, verified_user.email, PASSWORD)

    assert response.status_code == 429
    assert "bloquée" in response.content.decode()
    assert "_auth_user_id" not in client.session


def test_lock_ignores_email_case(client, verified_user):
    for email in ["awa@precisfc.test", "Awa@precisfc.test", "AWA@PRECISFC.TEST"] * 2:
        login(client, email, WRONG)

    assert login(client, verified_user.email, PASSWORD).status_code == 429


def test_lock_does_not_block_the_same_account_from_another_connection(client, verified_user):
    for _ in range(5):
        login(client, verified_user.email, WRONG, ip="10.0.0.66")

    response = login(client, verified_user.email, PASSWORD, ip="10.0.0.2")

    assert response.status_code == 302
    assert response["Location"] == reverse("accounts:profile")


def test_successful_login_resets_the_failure_counter(client, verified_user):
    for _ in range(4):
        login(client, verified_user.email, WRONG)
    login(client, verified_user.email, PASSWORD)
    client.logout()

    assert AccessAttempt.objects.count() == 0
    assert login(client, verified_user.email, WRONG).status_code == 200


def test_admin_login_is_protected_too(client):
    User.objects.create_superuser("direction@precisfc.test", PASSWORD)
    url = reverse("admin:login")
    for _ in range(5):
        client.post(url, {"username": "direction@precisfc.test", "password": WRONG})

    response = client.post(url, {"username": "direction@precisfc.test", "password": PASSWORD})

    assert response.status_code == 429


def test_profile_page_requires_login(client):
    response = client.get(reverse("accounts:profile"))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("account_login"))


def test_supporter_updates_own_profile(client, verified_user):
    client.force_login(verified_user)

    response = client.post(
        reverse("accounts:profile"),
        {
            "first_name": "Awa",
            "last_name": "Koné",
            "phone": "0701020304",
            "city": "Yamoussoukro",
            "country": "CI",
            "notify_news": "on",
        },
    )

    verified_user.refresh_from_db()
    assert response.status_code == 302
    assert verified_user.get_full_name() == "Awa Koné"
    assert str(verified_user.profile.phone) == "+2250701020304"
    assert verified_user.profile.notify_matches is False


def test_attack_spread_over_many_connections_is_still_limited(client, verified_user):
    for number in range(20):
        login(client, verified_user.email, WRONG, ip=f"10.1.0.{number}")

    response = login(client, verified_user.email, PASSWORD, ip="10.2.0.1")

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session
