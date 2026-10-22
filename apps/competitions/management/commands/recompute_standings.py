from django.core.management.base import BaseCommand

from apps.competitions.models import CompetitionSeason
from apps.competitions.services.recompute import recompute_edition


class Command(BaseCommand):
    help = (
        "Recalcule classements et statistiques de joueurs de toutes les éditions "
        "(normalement automatique ; utile après une importation de données)."
    )

    def handle(self, *args, **options):
        editions = CompetitionSeason.objects.select_related("competition", "season")
        for edition in editions:
            recompute_edition(edition.pk)
            self.stdout.write(f"{edition} : recalculé")
        self.stdout.write(self.style.SUCCESS(f"{editions.count()} édition(s) recalculée(s)."))
