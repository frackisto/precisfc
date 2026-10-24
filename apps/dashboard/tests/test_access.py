"""Accès au tableau de bord : chaque page, chaque section, pour chacun des 13 rôles."""

import pytest
from django.urls import reverse

from apps.accounts import roles
from apps.accounts.roles import ROLES, SUPERADMIN
from tests.factories import MatchFactory, UserFactory

pytestmark = pytest.mark.django_db

HOME = reverse("dashboard:home")
FINANCES = reverse("dashboard:finances")
EXPORT = reverse("dashboard:finances_export")
SCORES = reverse("dashboard:scores")
PAGES = [HOME, FINANCES, EXPORT, SCORES]

STAFF_ROLES = [key for key, role in ROLES.items() if role.is_staff] + [SUPERADMIN]
FINANCE_ROLES = {roles.DIRECTION, roles.TREASURER, SUPERADMIN}
SCORE_ROLES = {roles.CLUB_ADMIN, roles.SPORTING_DIRECTOR, roles.COACH, SUPERADMIN}


@pytest.mark.parametrize("url", PAGES)
def test_anonymous_visitor_is_sent_to_login(client, url):
    response = client.get(url)

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("account_login"))


@pytest.mark.parametrize("url", PAGES)
def test_supporter_without_role_is_refused(client, url):
    client.force_login(UserFactory())

    assert client.get(url).status_code == 403


@pytest.mark.parametrize("url", PAGES)
def test_ticket_agent_only_uses_the_scanning_screen(login, url):
    assert login(roles.TICKET_AGENT).get(url).status_code == 403


@pytest.mark.parametrize("url", PAGES)
def test_inactive_staff_account_is_refused(client, make_user, url):
    user = make_user(roles.DIRECTION)
    user.is_active = False
    user.save()
    client.force_login(user)

    # Un compte désactivé perd sa session : retour à la connexion.
    assert client.get(url).status_code in (302, 403)


@pytest.mark.parametrize("role", STAFF_ROLES)
def test_every_staff_role_opens_the_home_page(login, role):
    response = login(role).get(HOME)

    assert response.status_code == 200
    assert response["Cache-Control"].startswith("max-age=0")
    assert "no-store" in response["Cache-Control"]
    assert response["X-Robots-Tag"] == "noindex, nofollow"
    assert '<meta name="robots" content="noindex, nofollow">' in response.content.decode()


@pytest.mark.parametrize("role", STAFF_ROLES)
def test_finances_only_for_financial_roles(login, role):
    client = login(role)
    expected = 200 if role in FINANCE_ROLES else 403

    assert client.get(FINANCES).status_code == expected
    assert client.get(EXPORT).status_code == expected


@pytest.mark.parametrize("role", STAFF_ROLES)
def test_score_entry_only_for_roles_that_change_matches(login, role):
    expected = 200 if role in SCORE_ROLES else 403

    assert login(role).get(SCORES).status_code == expected


@pytest.mark.parametrize("role", STAFF_ROLES)
def test_score_update_refused_to_other_roles(login, role):
    if role in SCORE_ROLES:
        pytest.skip("Autorisé : voir test_scores.py")
    match = MatchFactory()

    response = login(role).post(
        reverse("dashboard:score_update", args=[match.pk]),
        {"home_score": 1, "away_score": 0, "status": "FINISHED"},
    )

    assert response.status_code == 403
    match.refresh_from_db()
    assert match.home_score is None


def test_pages_refuse_unsafe_methods(login):
    client = login(SUPERADMIN)

    assert client.post(HOME).status_code == 405
    assert client.post(FINANCES).status_code == 405
    assert client.get(reverse("dashboard:score_update", args=[1])).status_code == 405


# Sections affichées sur l'accueil (identifiants des blocs dans la page).
SECTION_IDS = {
    "finances": 'id="finances"',
    "shop": 'id="boutique"',
    "ticketing": 'id="billetterie"',
    "sport": 'id="sport"',
    "contents": 'id="contenus"',
    "relations": 'id="relations"',
}

# Rôle → sections visibles. Tout le reste doit être absent de la page.
VISIBLE = {
    SUPERADMIN: set(SECTION_IDS),
    roles.DIRECTION: {"finances", "shop", "ticketing", "sport", "contents", "relations"},
    roles.CLUB_ADMIN: {"sport", "contents", "relations"},
    roles.COMMUNICATION: {"sport", "contents", "relations"},
    roles.WRITER: {"sport", "contents"},
    roles.MEDIA_MANAGER: {"sport", "contents"},
    roles.SPORTING_DIRECTOR: {"sport"},
    roles.COACH: {"sport"},
    roles.SHOP_MANAGER: {"shop"},
    roles.TREASURER: {"finances", "shop", "ticketing"},
    roles.TICKETING_MANAGER: {"ticketing", "sport"},
    roles.ACADEMY_MANAGER: {"relations"},
}


@pytest.mark.parametrize("role", STAFF_ROLES)
def test_each_role_sees_only_its_sections(login, role):
    page = login(role).get(HOME).content.decode()

    shown = {key for key, marker in SECTION_IDS.items() if marker in page}

    assert shown == VISIBLE[role]


def test_financial_figures_never_reach_other_roles(login):
    """Même la recette par match (billetterie) est masquée sans droit financier."""
    page = login(roles.TICKETING_MANAGER).get(HOME).content.decode()

    assert "Chiffre d'affaires" not in page
    assert "Recette confirmée" not in page
    assert "Paiements manuels" not in page


def test_academy_figures_hidden_from_unrelated_roles(login):
    assert "Candidatures" not in login(roles.TREASURER).get(HOME).content.decode()
    assert "Candidatures" not in login(roles.SHOP_MANAGER).get(HOME).content.decode()


def test_direction_sees_every_count_but_no_personal_record(login):
    """Compteurs agrégés pour la direction, sans lien vers les fiches qu'elle ne peut
    pas ouvrir (candidatures d'enfants, comptes, messages)."""
    page = login(roles.DIRECTION).get(HOME).content.decode()

    assert "Candidatures à examiner" in page
    assert "Comptes actifs" in page
    assert "Nouveaux messages" in page
    assert reverse("admin:academy_application_changelist") not in page
    assert reverse("admin:accounts_user_changelist") not in page
    assert reverse("admin:contact_contactmessage_changelist") not in page


def test_navigation_lists_only_allowed_pages(login):
    treasurer = login(roles.TREASURER).get(HOME).content.decode()

    assert f'href="{FINANCES}"' in treasurer
    assert f'href="{SCORES}"' not in treasurer


@pytest.mark.parametrize(
    ("role", "expected", "absent"),
    [
        (roles.WRITER, ["Écrire un article"], ["Programmer un match", "Paramètres du club"]),
        (roles.SPORTING_DIRECTOR, ["Programmer un match", "Ajouter un joueur"], ["Écrire"]),
        (roles.SHOP_MANAGER, ["Ajouter un produit"], ["Écrire un article"]),
        (roles.CLUB_ADMIN, ["Paramètres du club", "Ajouter un partenaire"], ["Ajouter un produit"]),
        (SUPERADMIN, ["Comptes et rôles", "Ouvrir une vente de billets"], []),
        (roles.TREASURER, [], ["Écrire un article", "Comptes et rôles"]),
    ],
)
def test_shortcuts_follow_permissions(login, role, expected, absent):
    page = login(role).get(HOME).content.decode()

    for label in expected:
        assert label in page
    for label in absent:
        assert label not in page


def task_list(page: str) -> str:
    """Le seul bloc « À traiter » de la page."""
    start = page.index('id="titre-a-traiter"')
    return page[start : page.index("</section>", start)]


@pytest.mark.parametrize(
    ("role", "expected", "absent"),
    [
        (roles.TREASURER, ["Paiements manuels à confirmer"], ["Commandes à préparer"]),
        (roles.SHOP_MANAGER, ["Commandes à préparer", "Retours à traiter", "stock bas"], []),
        (roles.WRITER, ["Mes brouillons"], ["Articles à relire"]),
        (roles.COMMUNICATION, ["Articles à relire", "Messages de contact"], ["Mes brouillons"]),
        (roles.COACH, ["Scores à saisir"], ["Articles à relire"]),
        (roles.ACADEMY_MANAGER, ["Candidatures à examiner", "durée de conservation"], []),
        (roles.TICKETING_MANAGER, ["Réservations en attente"], ["Paiements manuels"]),
    ],
)
def test_tasks_follow_permissions(login, role, expected, absent):
    page = task_list(login(role).get(HOME).content.decode())

    for label in expected:
        assert label in page
    for label in absent:
        assert label not in page


def test_header_links_to_the_dashboard_for_staff_only(client, login):
    assert f'href="{HOME}"' not in client.get("/").content.decode()
    supporter = UserFactory()
    client.force_login(supporter)
    assert f'href="{HOME}"' not in client.get("/").content.decode()

    assert f'href="{HOME}"' in login(roles.WRITER).get("/").content.decode()


def test_robots_txt_keeps_the_dashboard_out_of_search_engines(client):
    assert "Disallow: /gestion/" in client.get("/robots.txt").content.decode()
