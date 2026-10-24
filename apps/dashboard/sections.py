"""Ce que chaque rôle voit sur le tableau de bord.

Tout découle des permissions Django (donc des rôles de ``apps/accounts/roles.py``) :
une section, une tâche ou un raccourci n'apparaît que si l'utilisateur a le droit
correspondant. Les chiffres d'une section masquée ne sont même pas calculés.
"""

from dataclasses import dataclass
from urllib.parse import urlencode

from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.accounts.roles import ALL_INDICATORS, FINANCIAL_REPORTS
from apps.core.utils import format_fcfa

from . import indicators

# Section du tableau de bord → permission qui l'affiche.
SECTION_PERMISSIONS = {
    "finances": FINANCIAL_REPORTS,
    "shop": "orders.view_order",
    "stock": "shop.view_productvariant",
    "ticketing": "ticketing.view_booking",
    "sport": "matches.view_match",
    "news": "news.view_article",
    "media": "media_library.view_album",
    "supporters": "accounts.view_user",
    "newsletter": "notifications.view_newslettersubscriber",
    "contact": "contact.view_contactmessage",
    "academy": "academy.view_application",
}


def visible_sections(user) -> set[str]:
    """Sections affichées. La direction voit tous les compteurs (chiffres agrégés), même
    ceux dont elle ne peut pas ouvrir les fiches (candidatures, comptes, messages)."""
    if user.has_perm(ALL_INDICATORS):
        return set(SECTION_PERMISSIONS)
    return {key for key, perm in SECTION_PERMISSIONS.items() if user.has_perm(perm)}


def admin_url(name: str, *args, **filters) -> str:
    """Adresse d'un écran de l'administration, avec des filtres de liste éventuels."""
    try:
        url = reverse(f"admin:{name}", args=args)
    except NoReverseMatch:
        return ""
    return f"{url}?{urlencode(filters)}" if filters else url


@dataclass(frozen=True)
class Task:
    label: str
    count: int
    url: str
    icon: str


def tasks(user, now=None) -> list[Task]:
    """Travail en attente pour cet utilisateur, avec le lien qui y mène."""
    now = now or timezone.now()
    today = timezone.localdate(now)
    result = []
    memo = {}

    def once(key, compute):
        # Un même calcul (articles, candidatures) sert à plusieurs tâches : une requête.
        if key not in memo:
            memo[key] = compute()
        return memo[key]

    def articles():
        return once("articles", lambda: indicators.article_counts(user))

    def applications():
        return once("applications", lambda: indicators.application_counts(today))

    def add(perm, label, icon, count_fn, url):
        if user.has_perm(perm):
            result.append(Task(label, count_fn(), url, icon))

    add(
        "news.publish_article",
        "Articles à relire",
        "journal-check",
        lambda: articles()["in_review"],
        admin_url("news_article_changelist", status__exact="IN_REVIEW"),
    )
    if user.has_perm("news.add_article") and not user.has_perm("news.publish_article"):
        result.append(
            Task(
                "Mes brouillons",
                articles()["my_drafts"],
                admin_url("news_article_changelist", status__exact="DRAFT", author__exact=user.pk),
                "pencil-square",
            )
        )
    add(
        "matches.change_match",
        "Scores à saisir",
        "123",
        lambda: indicators.matches_awaiting_score(user, now).count(),
        reverse("dashboard:scores"),
    )
    add(
        "payments.confirm_manual_payment",
        "Paiements manuels à confirmer",
        "cash-coin",
        lambda: indicators.pending_manual_payments()["count"],
        admin_url(
            "payments_payment_changelist",
            provider__exact="MANUAL",
            status__in=",".join(indicators.AWAITING_PAYMENT),
        ),
    )
    add(
        "orders.change_order",
        "Commandes à préparer",
        "box-seam",
        lambda: indicators.orders_overview()["to_prepare"],
        admin_url("orders_order_changelist", status__in=",".join(indicators.TO_PREPARE)),
    )
    add(
        "orders.change_returnrequest",
        "Retours à traiter",
        "arrow-return-left",
        indicators.open_returns_count,
        admin_url("orders_returnrequest_changelist", status__in=",".join(indicators.OPEN_RETURNS)),
    )
    add(
        "shop.change_productvariant",
        "Articles en stock bas",
        "exclamation-triangle",
        lambda: indicators.low_stock_variants().count(),
        f"{reverse('dashboard:home')}#stock",
    )
    add(
        "ticketing.change_booking",
        "Réservations en attente de paiement",
        "hourglass-split",
        lambda: indicators.pending_bookings_count(now),
        admin_url("ticketing_booking_changelist", status__exact="PENDING"),
    )
    add(
        "academy.change_application",
        "Candidatures à examiner",
        "person-vcard",
        lambda: applications()["to_review"],
        admin_url("academy_application_changelist", status__in="SUBMITTED,UNDER_REVIEW"),
    )
    add(
        "academy.change_application",
        "Candidatures à supprimer (durée de conservation dépassée)",
        "trash",
        lambda: applications()["retention_overdue"],
        admin_url("academy_application_changelist", retention_until__lt=today.isoformat()),
    )
    add(
        "contact.change_contactmessage",
        "Messages de contact non traités",
        "envelope-exclamation",
        lambda: indicators.contact_counts()["new"],
        admin_url("contact_contactmessage_changelist", status__exact="NEW"),
    )
    return result


@dataclass(frozen=True)
class Shortcut:
    label: str
    icon: str
    url_name: str
    perm: str


SHORTCUTS = [
    Shortcut("Écrire un article", "pencil", "news_article_add", "news.add_article"),
    Shortcut("Programmer un match", "calendar-plus", "matches_match_add", "matches.add_match"),
    Shortcut("Ajouter un joueur", "person-plus", "teams_player_add", "teams.add_player"),
    Shortcut(
        "Créer un album photo", "images", "media_library_album_add", "media_library.add_album"
    ),
    Shortcut(
        "Ajouter une vidéo", "camera-video", "media_library_video_add", "media_library.add_video"
    ),
    Shortcut("Ajouter une bannière", "card-image", "core_heroslide_add", "core.add_heroslide"),
    Shortcut("Ajouter un produit", "bag-plus", "shop_product_add", "shop.add_product"),
    Shortcut(
        "Ouvrir une vente de billets",
        "ticket-perforated",
        "ticketing_ticketcategory_add",
        "ticketing.add_ticketcategory",
    ),
    Shortcut("Ajouter un partenaire", "award", "partners_partner_add", "partners.add_partner"),
    Shortcut(
        "Préparer une newsletter",
        "envelope-paper",
        "notifications_newslettercampaign_add",
        "notifications.add_newslettercampaign",
    ),
    Shortcut(
        "Paramètres du club",
        "sliders",
        "core_clubsettings_changelist",
        "core.change_clubsettings",
    ),
    Shortcut("Comptes et rôles", "people", "accounts_user_changelist", "accounts.change_user"),
]


def shortcuts(user) -> list[dict]:
    result = []
    for shortcut in SHORTCUTS:
        if not user.has_perm(shortcut.perm):
            continue
        url = admin_url(shortcut.url_name)
        if url:
            result.append({"label": shortcut.label, "icon": shortcut.icon, "url": url})
    return result


def overview(user, *, season=None, now=None) -> list[dict]:
    """Les indicateurs clés du cahier des charges (section 15), chacun affiché seulement
    si l'utilisateur peut le voir. Rien n'est calculé pour un indicateur masqué."""
    now = now or timezone.now()
    month = indicators.this_month(timezone.localdate(now))
    everything = user.has_perm(ALL_INDICATORS)
    memo = {}

    def once(key, compute):
        if key not in memo:
            memo[key] = compute()
        return memo[key]

    def number(value):
        return format_fcfa(value, with_unit=False)

    def squad():
        return once("squad", indicators.squad_counts)

    def matches():
        return once("matches", lambda: indicators.match_counts(season))

    def orders():
        return once("orders", lambda: indicators.orders_count(month))

    def tickets():
        return once("tickets", lambda: indicators.tickets_sold(month))

    def stock():
        return once("stock", indicators.out_of_stock)

    def revenue():
        return once("revenue", lambda: indicators.revenue(month))

    items = [
        ("teams.view_player", "Joueurs", lambda: number(squad()["players"]), lambda: ""),
        ("teams.view_team", "Équipes", lambda: number(squad()["teams"]), lambda: ""),
        (
            "matches.view_match",
            "Matchs de la saison" if season else "Matchs",
            lambda: number(matches()["total"]),
            lambda: f"dont {number(matches()['played'])} joués",
        ),
        (
            "news.view_article",
            "Articles publiés",
            lambda: number(indicators.published_articles_count(now)),
            lambda: "",
        ),
        (
            "orders.view_order",
            "Commandes",
            lambda: number(orders()["total"]),
            lambda: f"{number(orders()['this_period'])} ce mois-ci",
        ),
        (
            FINANCIAL_REPORTS,
            "Chiffre d'affaires du mois",
            lambda: format_fcfa(revenue().total),
            lambda: "Paiements confirmés",
        ),
        (
            "ticketing.view_booking",
            "Billets vendus",
            lambda: number(tickets()["total"]),
            lambda: f"{number(tickets()['this_period'])} ce mois-ci",
        ),
        (
            "shop.view_productvariant",
            "Produits en rupture de stock",
            lambda: number(stock()["products"]),
            lambda: f"{number(stock()['variants'])} variante(s) épuisée(s)",
        ),
        (
            "accounts.view_user",
            "Utilisateurs inscrits",
            lambda: number(once("users", lambda: indicators.supporter_counts(month))["total"]),
            lambda: "Comptes actifs",
        ),
    ]
    result = []
    for perm, label, value, hint in items:
        if everything or user.has_perm(perm):
            result.append({"label": label, "value": value(), "hint": hint()})
    return result
