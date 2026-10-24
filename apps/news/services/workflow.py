"""Circuit de publication des articles : brouillon → relecture → programmé / publié → archivé.

Toutes les transitions passent par ces fonctions, qui vérifient le rôle (côté serveur)
et l'état de départ, et tracent la relecture. Le statut n'est jamais modifié à la main.

| Action | Qui | Depuis |
|---|---|---|
| Soumettre en relecture | l'auteur (rédacteur) ou une personne habilitée à publier | brouillon |
| Publier / programmer | habilité à publier | brouillon, relecture, programmé, archivé |
| Renvoyer en brouillon | habilité à publier | relecture, programmé, publié |
| Archiver | habilité à publier | publié, programmé |
"""

import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.permissions import can_change_article, can_publish_article
from apps.news.models import Article

Status = Article.Status


class WorkflowError(ValidationError):
    """Transition impossible depuis l'état actuel de l'article."""


def _require_status(article, *allowed):
    if article.status not in allowed:
        raise WorkflowError(
            f"Action impossible : l'article est « {article.get_status_display()} »."
        )


def _require(allowed: bool):
    if not allowed:
        raise PermissionDenied("Vous n'avez pas le droit d'effectuer cette action.")


def _reviewed(article, user, now):
    article.reviewed_by = user
    article.reviewed_at = now


@transaction.atomic
def submit_for_review(article: Article, user) -> Article:
    _require(can_change_article(user, article))
    _require_status(article, Status.DRAFT)
    if not article.title.strip() or not article.body.strip():
        raise WorkflowError("Un article soumis en relecture doit avoir un titre et un contenu.")
    article.status = Status.IN_REVIEW
    article.save(update_fields=["status", "updated_at"])
    return article


@transaction.atomic
def publish(article: Article, user, publish_at=None) -> Article:
    """Publie tout de suite, ou programme si la date de publication est dans le futur."""
    _require(can_publish_article(user))
    _require_status(article, Status.DRAFT, Status.IN_REVIEW, Status.SCHEDULED, Status.ARCHIVED)
    now = timezone.now()
    when = publish_at or article.publish_at or now
    if article.status == Status.ARCHIVED and when <= now:
        when = now  # republication : à la date du jour
    article.publish_at = when
    article.status = Status.SCHEDULED if when > now else Status.PUBLISHED
    _reviewed(article, user, now)
    article.save(update_fields=["status", "publish_at", "reviewed_by", "reviewed_at", "updated_at"])
    return article


@transaction.atomic
def return_to_draft(article: Article, user, note: str = "") -> Article:
    _require(can_publish_article(user))
    _require_status(article, Status.IN_REVIEW, Status.SCHEDULED, Status.PUBLISHED)
    article.status = Status.DRAFT
    if note:
        article.review_note = note
    _reviewed(article, user, timezone.now())
    article.save(
        update_fields=["status", "review_note", "reviewed_by", "reviewed_at", "updated_at"]
    )
    return article


@transaction.atomic
def archive(article: Article, user) -> Article:
    _require(can_publish_article(user))
    _require_status(article, Status.PUBLISHED, Status.SCHEDULED)
    article.status = Status.ARCHIVED
    article.save(update_fields=["status", "updated_at"])
    return article


def renew_preview_token(article: Article, user) -> Article:
    """Nouveau lien de prévisualisation : l'ancien cesse aussitôt de fonctionner."""
    _require(user.has_perm("news.view_article"))
    article.preview_token = uuid.uuid4()
    article.save(update_fields=["preview_token", "updated_at"])
    return article


def publish_due_articles(now=None) -> int:
    """Passe à « publié » les articles programmés dont l'heure est venue (tâche du cron).

    Ils sont déjà visibles dès leur heure (voir ``Article.objects.published``) : la
    tâche range seulement leur statut.
    """
    now = now or timezone.now()
    return Article.objects.filter(status=Status.SCHEDULED, publish_at__lte=now).update(
        status=Status.PUBLISHED, updated_at=now
    )


def available_actions(article: Article, user) -> list[tuple[str, str]]:
    """Boutons à proposer dans l'administration, selon le rôle et l'état de l'article."""
    actions = []
    if article.status == Status.DRAFT and can_change_article(user, article):
        actions.append(("submit", "Soumettre en relecture"))
    if can_publish_article(user):
        if article.status in (Status.DRAFT, Status.IN_REVIEW, Status.ARCHIVED):
            actions.append(("publish", "Publier ou programmer"))
        if article.status == Status.SCHEDULED:
            actions.append(("publish", "Mettre à jour la programmation"))
        if article.status in (Status.IN_REVIEW, Status.SCHEDULED, Status.PUBLISHED):
            actions.append(("return_to_draft", "Renvoyer en brouillon"))
        if article.status in (Status.PUBLISHED, Status.SCHEDULED):
            actions.append(("archive", "Archiver"))
    return actions
