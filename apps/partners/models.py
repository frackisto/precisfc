from django.db import models
from django.utils import timezone

from apps.core.fields import ImageField, URLField
from apps.core.models import SluggedModel


class PartnerQuerySet(models.QuerySet):
    def current(self, today=None):
        today = today or timezone.localdate()
        return self.filter(is_active=True).filter(
            models.Q(starts_on__isnull=True) | models.Q(starts_on__lte=today),
            models.Q(ends_on__isnull=True) | models.Q(ends_on__gte=today),
        )


class Partner(SluggedModel):
    class Tier(models.TextChoices):
        MAIN = "MAIN", "Partenaire principal"
        OFFICIAL = "OFFICIAL", "Partenaire officiel"
        TECHNICAL = "TECHNICAL", "Équipementier et partenaire technique"
        MEDIA = "MEDIA", "Partenaire média"
        INSTITUTIONAL = "INSTITUTIONAL", "Partenaire institutionnel"

    name = models.CharField("nom", max_length=150)
    logo = ImageField("logo", upload_to="partners/")
    tier = models.CharField("niveau", max_length=15, choices=Tier.choices)
    description = models.TextField("description", blank=True)
    url = URLField("site web", blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)
    starts_on = models.DateField("début du partenariat", null=True, blank=True)
    ends_on = models.DateField("fin du partenariat", null=True, blank=True)
    is_active = models.BooleanField("actif", default=True)

    objects = PartnerQuerySet.as_manager()

    class Meta:
        verbose_name = "partenaire"
        verbose_name_plural = "partenaires"
        ordering = ["tier", "order", "name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(starts_on__isnull=True)
                | models.Q(ends_on__isnull=True)
                | models.Q(ends_on__gte=models.F("starts_on")),
                name="partners_partner_ends_after_start",
                violation_error_message="La fin du partenariat ne peut précéder son début.",
            ),
        ]

    def __str__(self):
        return self.name
