"""Chaque écran de l'administration s'ouvre sans erreur pour un super administrateur."""

import pytest
from django.contrib import admin
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import ClubSettings

pytestmark = pytest.mark.django_db

PROJECT_MODELS = [model for model in admin.site._registry if model.__module__.startswith("apps.")]


@pytest.fixture
def admin_client(client):
    user = User.objects.create_superuser("direction@precisfc.test", "Mot-de-passe-admin-2026")
    client.force_login(user)
    return client


def admin_url(model, view, *args):
    return reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_{view}", args=args)


def test_every_project_model_is_registered():
    from django.apps import apps

    expected = {
        model
        for model in apps.get_models()
        if model.__module__.startswith("apps.") and not model._meta.auto_created
    }
    # Gérés dans des formulaires imbriqués (inlines) de leur objet parent.
    inline_only = {
        "accounts.profile",
        "accounts.address",
        "core.facilityphoto",
        "core.trophywin",
        "competitions.participation",
        "teams.playerphoto",
        "matches.lineupentry",
        "matches.matchevent",
        "matches.matchteamstat",
        "matches.matchschedulechange",
        "media_library.photo",
        "shop.productimage",
        "orders.cartitem",
        "orders.orderitem",
        "orders.orderstatusevent",
        "orders.promoredemption",
        "ticketing.ticket",
        "academy.applicationdocument",
    }
    missing = {model._meta.label_lower for model in expected - set(PROJECT_MODELS)} - inline_only

    assert missing == set()


@pytest.mark.parametrize("model", PROJECT_MODELS, ids=lambda model: model._meta.label)
def test_changelist_opens(admin_client, model):
    response = admin_client.get(admin_url(model, "changelist"), follow=True)

    assert response.status_code == 200


@pytest.mark.parametrize("model", PROJECT_MODELS, ids=lambda model: model._meta.label)
def test_add_form_opens_when_allowed(admin_client, model, rf):
    request = rf.get("/")
    request.user = User.objects.get(email="direction@precisfc.test")
    if not admin.site._registry[model].has_add_permission(request):
        pytest.skip("Création réservée aux services métier")

    response = admin_client.get(admin_url(model, "add"))

    assert response.status_code == 200


def test_club_settings_list_leads_to_the_single_form(admin_client):
    response = admin_client.get(admin_url(ClubSettings, "changelist"))

    assert response.status_code == 302
    assert response["Location"] == admin_url(ClubSettings, "change", 1)
    assert admin_client.get(admin_url(ClubSettings, "add")).status_code == 403
    assert admin_client.post(admin_url(ClubSettings, "delete", 1)).status_code == 403


def test_user_admin_shows_profile_only_after_creation(admin_client):
    add_page = admin_client.get(admin_url(User, "add"))
    user = User.objects.get(email="direction@precisfc.test")
    change_page = admin_client.get(admin_url(User, "change", user.pk))

    assert "profile-TOTAL_FORMS" not in add_page.content.decode()
    assert "profile-TOTAL_FORMS" in change_page.content.decode()
