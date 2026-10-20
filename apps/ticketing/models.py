import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel

MONEY = {"max_digits": 12, "decimal_places": 2, "validators": [MinValueValidator(0)]}


class TicketCategory(TimeStampedModel):
    match = models.ForeignKey(
        "matches.Match",
        verbose_name="match",
        on_delete=models.PROTECT,
        related_name="ticket_categories",
    )
    name = models.CharField("catégorie", max_length=100, help_text="Ex. Tribune d'honneur.")
    description = models.CharField("description", max_length=255, blank=True)
    price = models.DecimalField("prix (FCFA)", **MONEY)
    capacity = models.PositiveIntegerField("nombre de places", validators=[MinValueValidator(1)])
    max_per_order = models.PositiveSmallIntegerField(
        "maximum par réservation", default=4, validators=[MinValueValidator(1)]
    )
    sale_starts_at = models.DateTimeField("ouverture de la vente", null=True, blank=True)
    sale_ends_at = models.DateTimeField("fin de la vente", null=True, blank=True)
    is_active = models.BooleanField("en vente", default=True)

    class Meta:
        verbose_name = "catégorie de billets"
        verbose_name_plural = "catégories de billets"
        ordering = ["match", "price"]
        constraints = [
            models.UniqueConstraint(fields=["match", "name"], name="ticketing_category_unique"),
            models.CheckConstraint(
                condition=models.Q(price__gte=0, capacity__gte=1, max_per_order__gte=1),
                name="ticketing_category_positive_values",
            ),
            models.CheckConstraint(
                condition=models.Q(sale_starts_at__isnull=True)
                | models.Q(sale_ends_at__isnull=True)
                | models.Q(sale_ends_at__gt=models.F("sale_starts_at")),
                name="ticketing_category_sale_ends_after_start",
                violation_error_message="La fin de la vente doit suivre son ouverture.",
            ),
        ]

    def __str__(self):
        return f"{self.name} — {self.match}"


class Booking(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente de paiement"
        CONFIRMED = "CONFIRMED", "Confirmée"
        CANCELLED = "CANCELLED", "Annulée"
        EXPIRED = "EXPIRED", "Expirée"

    reference = models.CharField("référence", max_length=20, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="supporter",
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    match = models.ForeignKey(
        "matches.Match", verbose_name="match", on_delete=models.PROTECT, related_name="bookings"
    )
    status = models.CharField(
        "statut", max_length=10, choices=Status.choices, default=Status.PENDING
    )
    # Places bloquées jusqu'à cette date ; le cron libère les réservations expirées.
    expires_at = models.DateTimeField("expire le", null=True, blank=True)
    total = models.DecimalField("total (FCFA)", **MONEY)
    currency = models.CharField("devise", max_length=3, default="XOF", editable=False)
    cancelled_at = models.DateTimeField("annulée le", null=True, blank=True)
    cancel_reason = models.CharField("motif d'annulation", max_length=255, blank=True)

    class Meta:
        verbose_name = "réservation"
        verbose_name_plural = "réservations"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "expires_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total__gte=0), name="ticketing_booking_total_positive"
            ),
            models.CheckConstraint(
                condition=~models.Q(status="PENDING") | models.Q(expires_at__isnull=False),
                name="ticketing_booking_pending_expires",
                violation_error_message="Une réservation en attente doit avoir une échéance.",
            ),
        ]

    def __str__(self):
        return self.reference


class Ticket(TimeStampedModel):
    class Status(models.TextChoices):
        VALID = "VALID", "Valide"
        USED = "USED", "Utilisé"
        CANCELLED = "CANCELLED", "Annulé"

    booking = models.ForeignKey(
        Booking, verbose_name="réservation", on_delete=models.CASCADE, related_name="tickets"
    )
    category = models.ForeignKey(
        TicketCategory, verbose_name="catégorie", on_delete=models.PROTECT, related_name="tickets"
    )
    holder_name = models.CharField("titulaire", max_length=150)
    # Code du QR (signé à l'émission du billet PDF, étape 13).
    code = models.UUIDField("code", default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField("statut", max_length=10, choices=Status.choices, default=Status.VALID)
    used_at = models.DateTimeField("utilisé le", null=True, blank=True)
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="contrôlé par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    gate = models.CharField("porte", max_length=30, blank=True)

    class Meta:
        verbose_name = "billet"
        verbose_name_plural = "billets"
        ordering = ["booking", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(status="USED") | models.Q(used_at__isnull=False),
                name="ticketing_ticket_used_has_date",
                violation_error_message="Un billet utilisé doit avoir une date d'utilisation.",
            ),
        ]

    def __str__(self):
        return f"Billet {self.code} — {self.holder_name}"


class TicketScan(TimeStampedModel):
    """Journal de tous les contrôles, réussis ou non (codes inconnus compris)."""

    class Result(models.TextChoices):
        OK = "OK", "Accès autorisé"
        ALREADY_USED = "ALREADY_USED", "Déjà utilisé"
        INVALID = "INVALID", "Code invalide"
        CANCELLED = "CANCELLED", "Billet annulé"
        WRONG_MATCH = "WRONG_MATCH", "Autre match"
        EXPIRED = "EXPIRED", "Réservation expirée"

    ticket = models.ForeignKey(
        Ticket,
        verbose_name="billet",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scans",
    )
    raw_code = models.CharField("code lu", max_length=255)
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="agent",
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    result = models.CharField("résultat", max_length=15, choices=Result.choices)
    gate = models.CharField("porte", max_length=30, blank=True)
    scanned_at = models.DateTimeField("contrôlé le", auto_now_add=True)
    ip = models.GenericIPAddressField("adresse IP", null=True, blank=True)

    class Meta:
        verbose_name = "contrôle de billet"
        verbose_name_plural = "contrôles de billets"
        ordering = ["-scanned_at"]

    def __str__(self):
        return f"{self.scanned_at:%d/%m/%Y %H:%M} — {self.get_result_display()}"
