"""Recalcul du classement et des statistiques dès qu'une feuille de match change."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.competitions.models import Competition, Participation
from apps.competitions.services.recompute import schedule_recompute

from .models import LineupEntry, Match, MatchEvent


@receiver([post_save, post_delete], sender=Match)
def match_changed(sender, instance, raw=False, **kwargs):
    if not raw:
        schedule_recompute(
            instance.competition_season_id, getattr(instance, "_previous_edition_id", None)
        )


@receiver([post_save, post_delete], sender=MatchEvent)
@receiver([post_save, post_delete], sender=LineupEntry)
def match_sheet_changed(sender, instance, raw=False, **kwargs):
    if not raw:
        edition_id = (
            Match.objects.filter(pk=instance.match_id)
            .values_list("competition_season_id", flat=True)
            .first()
        )
        schedule_recompute(edition_id)


@receiver([post_save, post_delete], sender=Participation)
def participation_changed(sender, instance, raw=False, **kwargs):
    if not raw:
        schedule_recompute(instance.competition_season_id)


@receiver(post_save, sender=Competition)
def competition_rules_changed(sender, instance, raw=False, created=False, **kwargs):
    """Barème de points ou critères de départage modifiés : toutes les éditions."""
    if not raw and not created:
        schedule_recompute(*instance.editions.values_list("pk", flat=True))
