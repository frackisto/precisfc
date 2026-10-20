"""Les 13 rôles du club et leurs permissions.

Le super administrateur est l'indicateur « superutilisateur » de Django : il a tous les
droits, y compris ceux des fonctionnalités futures. Les 12 autres rôles sont des groupes
Django créés et tenus à jour par ``python manage.py setup_roles`` (idempotente : les
permissions d'un groupe sont exactement celles définies ici).

Les règles par objet (un entraîneur ne modifie que son équipe, un rédacteur que ses
brouillons) sont dans ``apps/accounts/permissions.py``.
"""

from dataclasses import dataclass

VIEW = ("view",)
VIEW_CHANGE = ("view", "change")
ALL = ("view", "add", "change", "delete")

DASHBOARD = "core.view_dashboard"
FINANCIAL_REPORTS = "core.view_financial_reports"


def perms(models: str, actions=ALL) -> frozenset[str]:
    """Permissions ``app.action_modele`` pour des modèles notés « app.modele app.modele »."""
    return frozenset(
        f"{model.split('.')[0]}.{action}_{model.split('.')[1]}"
        for model in models.split()
        for action in actions
    )


@dataclass(frozen=True)
class Role:
    key: str
    name: str
    description: str
    permissions: frozenset[str]
    # Accès à l'administration et au tableau de bord ; l'agent de contrôle n'utilise que
    # l'écran de contrôle des billets.
    is_staff: bool = True

    @property
    def all_permissions(self) -> frozenset[str]:
        return self.permissions | {DASHBOARD} if self.is_staff else self.permissions


CLUB_CONTENT = (
    "core.facility core.facilityphoto core.heroslide core.page core.value core.trophy "
    "core.trophywin core.president core.orgmember"
)
SPORT = (
    "teams.team teams.player teams.playerphoto teams.staff "
    "competitions.season competitions.club competitions.competition "
    "competitions.competitionseason competitions.participation "
    "matches.match matches.matchschedulechange matches.lineupentry matches.matchevent "
    "matches.matchteamstat"
)
COMPUTED = "competitions.standing competitions.playerseasonstat"
NEWS = "news.article news.category news.tag"
MEDIA = "media_library.album media_library.photo media_library.video"
CATALOGUE = "shop.productcategory shop.product shop.productimage shop.productvariant"
ACADEMY_PUBLIC = "academy.agecategory academy.trainingprogram academy.academyevent"

SUPERADMIN = "superadmin"
DIRECTION = "direction"
CLUB_ADMIN = "club_admin"
COMMUNICATION = "communication"
WRITER = "writer"
MEDIA_MANAGER = "media_manager"
SPORTING_DIRECTOR = "sporting_director"
COACH = "coach"
SHOP_MANAGER = "shop_manager"
TREASURER = "treasurer"
TICKETING_MANAGER = "ticketing_manager"
TICKET_AGENT = "ticket_agent"
ACADEMY_MANAGER = "academy_manager"

SUPERADMIN_LABEL = "Super administrateur"

ROLES: dict[str, Role] = {
    role.key: role
    for role in [
        Role(
            DIRECTION,
            "Direction",
            "Consulte tous les indicateurs et les données du club, sans rien modifier.",
            perms(
                f"{CLUB_CONTENT} core.clubsettings {SPORT} {COMPUTED} {NEWS} {MEDIA} "
                f"{CATALOGUE} orders.order payments.payment ticketing.ticketcategory "
                "ticketing.booking partners.partner notifications.newslettercampaign",
                VIEW,
            )
            | {FINANCIAL_REPORTS},
        ),
        Role(
            CLUB_ADMIN,
            "Administrateur du club",
            "Gère les contenus, les équipes, les partenaires et les paramètres du club.",
            perms(f"{CLUB_CONTENT} {SPORT} {NEWS} {MEDIA} partners.partner contact.faqitem")
            | perms("notifications.newslettercampaign")
            | perms("core.clubsettings contact.contactmessage", VIEW_CHANGE)
            | perms(f"{COMPUTED} notifications.newslettersubscriber accounts.user", VIEW)
            | {"news.publish_article"},
        ),
        Role(
            COMMUNICATION,
            "Responsable communication",
            "Relit, valide et publie les articles ; gère médias, bannières et newsletter.",
            perms(f"{NEWS} {MEDIA} core.heroslide core.page contact.faqitem")
            | perms("notifications.newslettercampaign")
            | perms("contact.contactmessage", VIEW_CHANGE)
            | perms(
                "partners.partner notifications.newslettersubscriber matches.match teams.player",
                VIEW,
            )
            | {"news.publish_article"},
        ),
        Role(
            WRITER,
            "Rédacteur",
            "Écrit des articles et les soumet en relecture ; ne publie pas.",
            perms("news.article", ("view", "add", "change"))
            | perms("news.tag", ("view", "add"))
            | perms(f"news.category {MEDIA} matches.match teams.player", VIEW),
        ),
        Role(
            MEDIA_MANAGER,
            "Gestionnaire médias",
            "Gère les albums photo et les vidéos.",
            perms(MEDIA) | perms("matches.match competitions.season news.article", VIEW),
        ),
        Role(
            SPORTING_DIRECTOR,
            "Responsable sportif",
            "Gère équipes, joueurs, staff, compétitions, matchs et scores.",
            perms(SPORT) | perms(f"{COMPUTED} core.facility academy.agecategory", VIEW),
        ),
        Role(
            COACH,
            "Entraîneur",
            "Saisit compositions, événements et statistiques des matchs de son équipe.",
            perms("matches.lineupentry matches.matchevent matches.matchteamstat")
            | perms("matches.match teams.player", VIEW_CHANGE)
            | perms(
                "teams.team teams.playerphoto teams.staff competitions.season "
                f"competitions.club competitions.competition competitions.competitionseason "
                f"{COMPUTED}",
                VIEW,
            ),
        ),
        Role(
            SHOP_MANAGER,
            "Responsable boutique",
            "Gère le catalogue, les stocks, les commandes, la livraison et les retours.",
            perms(f"{CATALOGUE} orders.shippingmethod orders.promocode")
            | perms("shop.stockmovement", ("view", "add"))
            | perms("orders.order orders.returnrequest", VIEW_CHANGE)
            | perms(
                "shop.wishlistitem orders.cart orders.cartitem orders.orderitem "
                "orders.orderstatusevent orders.promoredemption payments.payment",
                VIEW,
            ),
        ),
        Role(
            TREASURER,
            "Trésorier",
            "Confirme les paiements manuels et consulte les indicateurs financiers.",
            perms(
                "payments.payment payments.webhookevent orders.order orders.orderitem "
                "ticketing.booking ticketing.ticket",
                VIEW,
            )
            | {"payments.confirm_manual_payment", FINANCIAL_REPORTS},
        ),
        Role(
            TICKETING_MANAGER,
            "Responsable billetterie",
            "Ouvre la vente des billets (catégories, prix, quotas) et suit les réservations.",
            perms("ticketing.ticketcategory")
            | perms("ticketing.booking ticketing.ticket", VIEW_CHANGE)
            | perms("ticketing.ticketscan matches.match payments.payment", VIEW)
            | {"ticketing.scan_ticket"},
        ),
        Role(
            TICKET_AGENT,
            "Agent de contrôle",
            "Contrôle les billets à l'entrée du stade, et rien d'autre.",
            perms("ticketing.ticket", VIEW) | {"ticketing.scan_ticket"},
            is_staff=False,
        ),
        Role(
            ACADEMY_MANAGER,
            "Responsable du centre de formation",
            "Gère le centre de formation, les candidatures et leurs documents privés.",
            perms(ACADEMY_PUBLIC)
            | perms("academy.application", VIEW_CHANGE)
            | perms("academy.applicationdocument teams.team teams.player", VIEW)
            | {"academy.download_private_document"},
        ),
    ]
}

STAFF_GROUP_NAMES = frozenset(role.name for role in ROLES.values() if role.is_staff)


def user_role_keys(user) -> set[str]:
    """Rôles de l'utilisateur (mis en cache sur l'objet pour la requête en cours)."""
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return set()
    if not hasattr(user, "_role_keys"):
        names = set(user.groups.values_list("name", flat=True))
        user._role_keys = {role.key for role in ROLES.values() if role.name in names}
        if user.is_superuser:
            user._role_keys.add(SUPERADMIN)
    return user._role_keys


def has_role(user, *keys: str) -> bool:
    return bool(user_role_keys(user) & set(keys))


def assign_role(user, key: str) -> None:
    from django.contrib.auth.models import Group

    group, _ = Group.objects.get_or_create(name=ROLES[key].name)
    user.groups.add(group)
    user.__dict__.pop("_role_keys", None)


def should_be_staff(user) -> bool:
    """Accès à l'administration : superutilisateur ou au moins un rôle interne."""
    return user.is_superuser or user.groups.filter(name__in=STAFF_GROUP_NAMES).exists()
