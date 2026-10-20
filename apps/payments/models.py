import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class Payment(TimeStampedModel):
    """Paiement d'une commande ou d'une réservation. Aucune donnée de carte n'est stockée."""

    class Provider(models.TextChoices):
        SANDBOX = "SANDBOX", "Bac à sable (tests)"
        MANUAL = "MANUAL", "Paiement manuel"

    class Method(models.TextChoices):
        CASH = "CASH", "Espèces"
        MOBILE_MONEY_MANUAL = "MOBILE_MONEY_MANUAL", "Mobile Money (confirmé manuellement)"
        BANK_TRANSFER = "BANK_TRANSFER", "Virement bancaire"
        CARD = "CARD", "Carte bancaire"

    class Status(models.TextChoices):
        INITIATED = "INITIATED", "Initié"
        PENDING = "PENDING", "En attente"
        SUCCEEDED = "SUCCEEDED", "Réussi"
        FAILED = "FAILED", "Échoué"
        CANCELLED = "CANCELLED", "Annulé"
        EXPIRED = "EXPIRED", "Expiré"
        REFUNDED = "REFUNDED", "Remboursé"

    uuid = models.UUIDField("identifiant", default=uuid.uuid4, unique=True, editable=False)
    order = models.ForeignKey(
        "orders.Order",
        verbose_name="commande",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
    )
    booking = models.ForeignKey(
        "ticketing.Booking",
        verbose_name="réservation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
    )
    provider = models.CharField("fournisseur", max_length=20, choices=Provider.choices)
    method = models.CharField("moyen de paiement", max_length=20, choices=Method.choices)
    amount = models.DecimalField(
        "montant (FCFA)", max_digits=12, decimal_places=2, validators=[MinValueValidator(1)]
    )
    currency = models.CharField("devise", max_length=3, default="XOF", editable=False)
    status = models.CharField(
        "statut", max_length=10, choices=Status.choices, default=Status.INITIATED
    )
    # Ex. numéro de transaction Mobile Money saisi par l'agent. NULL tant qu'il est inconnu,
    # pour que la contrainte d'unicité ne s'applique qu'aux références réellement saisies.
    provider_reference = models.CharField(  # noqa: DJ001
        "référence de la transaction", max_length=100, null=True, blank=True
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="confirmé par",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    confirmed_at = models.DateTimeField("confirmé le", null=True, blank=True)
    failure_reason = models.CharField("motif de l'échec", max_length=255, blank=True)

    class Meta:
        verbose_name = "paiement"
        verbose_name_plural = "paiements"
        permissions = [("confirm_manual_payment", "Peut confirmer un paiement manuel")]
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(order__isnull=False, booking__isnull=True)
                | models.Q(order__isnull=True, booking__isnull=False),
                name="payments_payment_order_xor_booking",
                violation_error_message="Un paiement concerne une commande ou une réservation.",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="payments_payment_amount_positive"
            ),
            # Une même transaction Mobile Money ne peut pas valider deux paiements.
            models.UniqueConstraint(
                fields=["provider", "provider_reference"],
                name="payments_payment_unique_reference",
                violation_error_message="Cette référence de transaction est déjà utilisée.",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="SUCCEEDED") | models.Q(confirmed_at__isnull=False),
                name="payments_payment_succeeded_is_confirmed",
                violation_error_message="Un paiement réussi doit avoir une date de confirmation.",
            ),
        ]

    def __str__(self):
        return f"Paiement {self.uuid} ({self.get_status_display()})"


class WebhookEvent(TimeStampedModel):
    """Notification reçue d'un agrégateur de paiement (utilisée à partir de la V2)."""

    provider = models.CharField("fournisseur", max_length=20)
    event_id = models.CharField("identifiant de l'événement", max_length=100)
    signature_valid = models.BooleanField("signature valide", default=False)
    payload = models.JSONField("contenu")
    received_at = models.DateTimeField("reçu le", auto_now_add=True)
    processed_at = models.DateTimeField("traité le", null=True, blank=True)
    processing_error = models.TextField("erreur de traitement", blank=True)
    payment = models.ForeignKey(
        Payment,
        verbose_name="paiement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="webhook_events",
    )

    class Meta:
        verbose_name = "notification de paiement"
        verbose_name_plural = "notifications de paiement"
        ordering = ["-received_at"]
        constraints = [
            # Idempotence : un même événement n'est jamais traité deux fois.
            models.UniqueConstraint(
                fields=["provider", "event_id"], name="payments_webhook_unique"
            ),
        ]

    def __str__(self):
        return f"{self.provider} {self.event_id}"
