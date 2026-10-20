import secrets

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


def new_token():
    return secrets.token_urlsafe(32)


class NewsletterSubscriber(TimeStampedModel):
    """Abonné à la newsletter, inscrit avec double confirmation par e-mail."""

    email = models.EmailField("e-mail", unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="compte",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="newsletter_subscriptions",
    )
    is_confirmed = models.BooleanField("confirmé", default=False)
    confirm_token = models.CharField(
        "jeton de confirmation", max_length=64, unique=True, default=new_token, editable=False
    )
    confirmed_at = models.DateTimeField("confirmé le", null=True, blank=True)
    unsubscribed_at = models.DateTimeField("désinscrit le", null=True, blank=True)
    source = models.CharField(
        "origine", max_length=50, blank=True, help_text="Ex. pied de page, inscription."
    )

    class Meta:
        verbose_name = "abonné à la newsletter"
        verbose_name_plural = "abonnés à la newsletter"
        ordering = ["-created_at"]

    def __str__(self):
        return self.email


class NewsletterCampaign(TimeStampedModel):
    """Campagne envoyée par lots par le cron (limites d'envoi de l'hébergement)."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        QUEUED = "QUEUED", "En file d'attente"
        SENDING = "SENDING", "Envoi en cours"
        SENT = "SENT", "Envoyée"

    subject = models.CharField("objet", max_length=200)
    body = models.TextField("contenu")
    status = models.CharField("statut", max_length=10, choices=Status.choices, default=Status.DRAFT)
    sent_count = models.PositiveIntegerField("envois effectués", default=0, editable=False)
    batch_size = models.PositiveSmallIntegerField(
        "taille des lots", default=50, validators=[MinValueValidator(1)]
    )

    class Meta:
        verbose_name = "campagne de newsletter"
        verbose_name_plural = "campagnes de newsletter"
        ordering = ["-created_at"]

    def __str__(self):
        return self.subject


class EmailLog(TimeStampedModel):
    class Status(models.TextChoices):
        SENT = "SENT", "Envoyé"
        FAILED = "FAILED", "Échec"

    to = models.EmailField("destinataire")
    template = models.CharField("modèle", max_length=100)
    subject = models.CharField("objet", max_length=255)
    status = models.CharField("statut", max_length=10, choices=Status.choices)
    error = models.TextField("erreur", blank=True)

    class Meta:
        verbose_name = "e-mail envoyé"
        verbose_name_plural = "journal des e-mails"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.subject} → {self.to}"
