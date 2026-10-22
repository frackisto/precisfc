"""Recalcul automatique du classement et des statistiques d'une édition.

Appelé après chaque modification d'un match, d'une composition, d'un événement ou d'un
participant, une fois la transaction validée (jamais sur des données à moitié saisies).
"""

from contextlib import contextmanager
from contextvars import ContextVar

from django.db import transaction

from apps.competitions.models import CompetitionSeason

from .player_stats import update_player_stats
from .standings import update_standings

_suspended: ContextVar[bool] = ContextVar("recompute_suspended", default=False)


def recompute_edition(edition_id: int) -> None:
    edition = CompetitionSeason.objects.select_related("competition").filter(pk=edition_id).first()
    if edition is None:  # édition supprimée entre-temps
        return
    update_standings(edition)
    update_player_stats(edition)


def schedule_recompute(*edition_ids) -> None:
    if _suspended.get():
        return
    for edition_id in {edition_id for edition_id in edition_ids if edition_id}:
        transaction.on_commit(lambda edition_id=edition_id: recompute_edition(edition_id))


@contextmanager
def recompute_suspended():
    """Saisie en masse (import, démonstration) : pas de recalcul à chaque enregistrement.

    L'appelant lance ensuite ``recompute_edition`` une seule fois par édition.
    """
    token = _suspended.set(True)
    try:
        yield
    finally:
        _suspended.reset(token)
