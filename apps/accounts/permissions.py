"""Règles d'accès par objet, appliquées côté serveur (administration, vues, API).

Les permissions Django disent ce qu'un rôle peut faire sur un type d'objet ; ces
fonctions précisent sur quels objets : un entraîneur ne modifie que les joueurs et
matchs de son équipe, un rédacteur que ses propres brouillons.
"""

from django.core.exceptions import PermissionDenied

from apps.news.models import Article
from apps.teams.models import Staff, Team


def team_scope(user) -> set[int] | None:
    """Équipes que l'utilisateur peut gérer : ``None`` = toutes.

    Toutes pour qui a le droit de modifier les équipes (responsable sportif,
    administrateur du club, super administrateur) ; sinon celles qu'il entraîne.
    """
    if user.is_superuser or user.has_perm("teams.change_team"):
        return None
    if not hasattr(user, "_coached_team_ids"):
        staff_teams = Staff.objects.filter(user=user, team__isnull=False).values_list(
            "team_id", flat=True
        )
        head_coach_teams = Team.objects.filter(head_coach__user=user).values_list("pk", flat=True)
        user._coached_team_ids = set(staff_teams) | set(head_coach_teams)
    return user._coached_team_ids


def _in_scope(user, team_id) -> bool:
    scope = team_scope(user)
    return scope is None or team_id in scope


def can_change_player(user, player) -> bool:
    return user.has_perm("teams.change_player") and _in_scope(user, player.team_id)


def can_change_match(user, match) -> bool:
    return user.has_perm("matches.change_match") and _in_scope(
        user, match.competition_season.team_id
    )


def can_publish_article(user) -> bool:
    return user.has_perm("news.publish_article")


def can_change_article(user, article) -> bool:
    """Un rédacteur ne modifie que ses brouillons ; la relecture et la publication
    reviennent aux personnes habilitées à publier."""
    if not user.has_perm("news.change_article"):
        return False
    if can_publish_article(user):
        return True
    return article.author_id == user.pk and article.status == Article.Status.DRAFT


def can_confirm_manual_payment(user) -> bool:
    return user.has_perm("payments.confirm_manual_payment")


def can_scan_tickets(user) -> bool:
    return user.has_perm("ticketing.scan_ticket")


def can_download_application_document(user) -> bool:
    return user.has_perm("academy.download_private_document")


def require(allowed: bool) -> None:
    """À appeler dans une vue : 403 si la règle refuse l'accès."""
    if not allowed:
        raise PermissionDenied
