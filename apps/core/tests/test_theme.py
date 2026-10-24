"""Gabarit commun, thème du club, mode sombre, navigation sans JavaScript, pages d'erreur."""

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.template.loader import render_to_string
from django.test import Client, override_settings
from django.urls import path, reverse

from apps.core.context_processors import THEME_COOKIE
from apps.core.models import ClubSettings
from apps.core.navigation import MenuItem, build_menu
from config import urls as site_urls
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def html(response):
    return response.content.decode()


# --- Gabarit commun ------------------------------------------------------------------


def test_home_page_uses_the_common_layout(client):
    page = html(client.get(reverse("core:home")))

    assert '<html lang="fr" class="no-js"' in page
    assert 'href="#contenu"' in page and 'id="contenu"' in page
    assert 'aria-label="Navigation principale"' in page
    assert "Precis FC" in page
    assert '<meta name="csrf-token"' in page
    assert "<footer" in page


def test_club_settings_appear_in_the_layout(client):
    club = ClubSettings.load()
    club.slogan = "Ensemble vers les sommets"
    club.phone = "+225 07 01 02 03 04"
    club.facebook_url = "https://facebook.com/precisfc"
    club.save()

    page = html(client.get(reverse("core:home")))

    assert "Ensemble vers les sommets" in page
    assert 'href="tel:+2250701020304"' in page
    assert 'href="https://facebook.com/precisfc"' in page
    assert 'rel="noopener"' in page


def test_club_settings_are_cached_and_refreshed_on_save(django_assert_num_queries):
    ClubSettings.load().save()
    ClubSettings.cached()

    with django_assert_num_queries(1):  # lecture du cache en base uniquement
        ClubSettings.cached()

    club = ClubSettings.load()
    club.name = "Precis Football Club"
    club.save()
    assert ClubSettings.cached().name == "Precis Football Club"


def test_anonymous_visitor_sees_login_and_signup_links(client):
    page = html(client.get(reverse("core:home")))

    assert reverse("account_login") in page
    assert reverse("account_signup") in page
    assert "Administration" not in page


def test_signup_link_is_hidden_when_signups_are_closed(client, settings):
    settings.ACCOUNT_SIGNUP_OPEN = False

    page = html(client.get(reverse("core:home")))

    assert reverse("account_signup") not in page
    assert reverse("account_login") in page


def test_supporter_sees_account_and_logout_form_but_no_admin(client):
    client.force_login(UserFactory())

    page = html(client.get(reverse("core:home")))

    assert reverse("accounts:profile") in page
    assert f'action="{reverse("account_logout")}"' in page
    assert reverse("admin:index") not in page


def test_staff_sees_the_dashboard_link(client):
    # Le tableau de bord (étape 10) mène ensuite à l'administration.
    client.force_login(UserFactory(is_superuser=True))

    assert reverse("dashboard:home") in html(client.get(reverse("core:home")))


# --- Menu ------------------------------------------------------------------------------


def test_menu_only_lists_pages_that_exist():
    items = [MenuItem("Accueil", "core:home", "house"), MenuItem("Boutique", "shop:index", "bag")]

    menu = build_menu("/", items)

    assert [entry["label"] for entry in menu] == ["Accueil"]
    assert menu[0]["active"] is True


def test_menu_marks_the_current_section():
    items = [MenuItem("Accueil", "core:home", "house"), MenuItem("Compte", "accounts:profile", "x")]

    menu = build_menu(reverse("accounts:profile"), items)

    assert [entry["active"] for entry in menu] == [False, True]


def test_navigation_works_without_javascript(client):
    page = html(client.get(reverse("core:home")))
    css = Path(finders.find("css/site.css")).read_text(encoding="utf-8")

    # Sans JS, la classe no-js déplie le menu ; chaque rubrique est un vrai lien.
    assert ".no-js .navbar-collapse { display: block !important; }" in css
    nav = page.split('id="menu-principal"', 1)[1].split("</nav>", 1)[0]
    assert re.search(r'<a class="nav-link[^"]*" href="/"', nav)
    # Déconnexion et changement de thème : des formulaires, pas des scripts.
    assert '<form method="post" action="/theme/"' in page


# --- Thème et mode sombre -------------------------------------------------------------------


def test_theme_stylesheet_uses_club_colors(client):
    club = ClubSettings.load()
    club.color_primary = "#E30613"
    club.save()

    response = client.get(reverse("core:theme_css"))

    assert response["Content-Type"].startswith("text/css")
    assert "--pfc-primary: #E30613;" in html(response)
    assert "max-age=31536000" in response["Cache-Control"]


def test_theme_stylesheet_url_changes_when_settings_change(client):
    ClubSettings.load()
    ClubSettings.objects.filter(pk=1).update(updated_at=datetime(2020, 1, 1, tzinfo=UTC))
    cache.clear()
    before = re.search(r"theme\.css\?v=(\d+)", html(client.get("/"))).group(1)

    ClubSettings.load().save()
    after = re.search(r"theme\.css\?v=(\d+)", html(client.get("/"))).group(1)

    assert before == "20200101000000"
    assert after != before


@pytest.mark.parametrize(("choice", "attribute"), [("dark", "dark"), ("light", "light")])
def test_theme_choice_is_remembered_and_rendered(client, choice, attribute):
    response = client.post(reverse("core:set_theme"), {"theme": choice, "next": "/compte/login/"})

    assert response.status_code == 302
    assert response["Location"] == "/compte/login/"
    assert response.cookies[THEME_COOKIE].value == choice
    assert f'data-bs-theme="{attribute}" data-theme-choice="{choice}"' in html(client.get("/"))


def test_without_choice_the_theme_follows_the_system(client):
    page = html(client.get("/"))

    assert 'data-theme-choice="auto"' in page
    assert "theme-init.js" in page.split("</head>")[0]


def test_theme_switch_ignores_unknown_values_and_foreign_redirects(client):
    response = client.post(
        reverse("core:set_theme"), {"theme": "rose", "next": "https://site-pirate.example/"}
    )

    assert response["Location"] == reverse("core:home")
    assert THEME_COOKIE not in response.cookies


def test_theme_switch_requires_post(client):
    assert client.get(reverse("core:set_theme")).status_code == 405


def test_theme_switch_is_protected_by_csrf():
    response = Client(enforce_csrf_checks=True).post(reverse("core:set_theme"), {"theme": "dark"})

    assert response.status_code == 403
    assert "Formulaire expiré" in html(response)


# --- Fichiers statiques ---------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "vendor/bootstrap/css/bootstrap.min.css",
        "vendor/bootstrap/js/bootstrap.bundle.min.js",
        "vendor/bootstrap-icons/bootstrap-icons.min.css",
        "vendor/bootstrap-icons/fonts/bootstrap-icons.woff2",
        "vendor/jquery/jquery.min.js",
        "css/site.css",
        "css/error-500.css",
        "js/theme-init.js",
        "js/app.js",
    ],
)
def test_static_files_are_hosted_locally(path):
    assert finders.find(path), path


def test_app_js_adds_the_csrf_token_to_ajax_requests():
    script = Path(finders.find("js/app.js")).read_text(encoding="utf-8")

    assert 'meta[name="csrf-token"]' in script
    assert "X-CSRFToken" in script
    assert "ajaxSetup" in script and "window.fetch" in script


def test_pages_load_no_external_resources(client):
    page = html(client.get("/"))

    # Ressources téléchargées par le navigateur : scripts, feuilles de style, images.
    # (Les liens canoniques et Open Graph sont des adresses absolues, pas des ressources.)
    external = r'(<script[^>]*src|<link[^>]*rel="stylesheet"[^>]*href|<img[^>]*src)="(https?:)?//'
    assert not re.search(external, page)


# --- Pages d'erreur ------------------------------------------------------------------


def test_404_page_keeps_the_site_layout(client):
    response = client.get("/cette-page-n-existe-pas/")

    assert response.status_code == 404
    assert "Page introuvable" in html(response)
    assert 'aria-label="Navigation principale"' in html(response)


def deny(request):
    raise PermissionDenied


def crash(request):
    raise RuntimeError("panne simulée")


# Pages de test ajoutées aux URL du site (les gabarits ont besoin des vraies URL).
urlpatterns = [path("refuse/", deny), path("panne/", crash), *site_urls.urlpatterns]


@override_settings(ROOT_URLCONF=__name__)
def test_403_page(client):
    response = client.get("/refuse/")

    assert response.status_code == 403
    assert "Accès refusé" in html(response)


@override_settings(ROOT_URLCONF=__name__)
def test_500_page_is_shown_on_unexpected_error():
    response = Client(raise_request_exception=False).get("/panne/")

    assert response.status_code == 500
    assert "Une erreur est survenue" in html(response)


def test_500_page_renders_without_database_or_context():
    page = render_to_string("500.html")

    assert "Une erreur est survenue" in page
    assert "style=" not in page


def test_400_page_template():
    page = render_to_string("400.html", {"club": ClubSettings.load()})

    assert "Requête invalide" in page


# --- Pages de compte (allauth) ----------------------------------------------------------------


def test_login_page_uses_the_site_theme(client):
    page = html(client.get(reverse("account_login")))

    assert 'aria-label="Navigation principale"' in page
    assert 'class="auth-card' in page
    assert re.search(
        r'<input[^>]*class="[^"]*form-control[^"]*"[^>]*name="login"|name="login"[^>]*class="[^"]*form-control',
        page,
    )
    assert 'class="btn btn-primary"' in page


def test_signup_errors_are_shown_with_bootstrap_styles(client):
    page = html(
        client.post(
            reverse("account_signup"),
            {"email": "pas-une-adresse", "password1": "a", "password2": "b"},
        )
    )

    assert "is-invalid" in page
    assert "invalid-feedback" in page


def test_profile_page_uses_bootstrap_forms(client):
    client.force_login(UserFactory())

    page = html(client.get(reverse("accounts:profile")))

    assert "form-control" in page
    assert "Mon compte" in page


def test_card_images_keep_their_proportions_whatever_the_card_width():
    # Sans « height: auto », l'attribut height de <img> impose une hauteur fixe et l'image
    # est rognée sur les côtés dans une carte étroite (titre coupé, visages coupés…).
    css = Path(finders.find("css/site.css")).read_text(encoding="utf-8")

    for selector in (".article-cover {", ".player-card-photo {", ".photo-grid img {"):
        rule = css.split(selector, 1)[1].split("}", 1)[0]
        assert "height: auto" in rule, selector
