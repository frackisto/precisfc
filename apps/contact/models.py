from django.conf import settings
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

from apps.core.models import TimeStampedModel
from apps.core.storage import private_storage
from apps.core.utils import RandomFilename


class ContactMessage(TimeStampedModel):
    class Kind(models.TextChoices):
        GENERAL = "GENERAL", "Contact général"
        PARTNERSHIP = "PARTNERSHIP", "Partenariat"
        RECRUITMENT = "RECRUITMENT", "Recrutement sportif"
        PRESS = "PRESS", "Presse"

    class Status(models.TextChoices):
        NEW = "NEW", "Nouveau"
        IN_PROGRESS = "IN_PROGRESS", "En cours"
        CLOSED = "CLOSED", "Traité"
        SPAM = "SPAM", "Indésirable"

    kind = models.CharField("type", max_length=15, choices=Kind.choices, default=Kind.GENERAL)
    name = models.CharField("nom", max_length=150)
    email = models.EmailField("e-mail")
    phone = PhoneNumberField("téléphone", blank=True)
    organisation = models.CharField("organisation", max_length=150, blank=True)
    subject = models.CharField("objet", max_length=200)
    message = models.TextField("message")
    attachment = models.FileField(
        "pièce jointe",
        storage=private_storage,
        upload_to=RandomFilename("contact"),
        blank=True,
    )
    status = models.CharField("statut", max_length=15, choices=Status.choices, default=Status.NEW)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="traité par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    # Empreinte de l'adresse IP (antispam) : l'adresse elle-même n'est pas conservée.
    ip_hash = models.CharField("empreinte IP", max_length=64, blank=True, editable=False)

    class Meta:
        verbose_name = "message de contact"
        verbose_name_plural = "messages de contact"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.subject} — {self.name}"


class FaqItem(TimeStampedModel):
    category = models.CharField("rubrique", max_length=100, blank=True)
    question = models.CharField("question", max_length=255)
    answer = models.TextField("réponse")
    order = models.PositiveSmallIntegerField("ordre", default=0)
    is_published = models.BooleanField("publiée", default=True)

    class Meta:
        verbose_name = "question fréquente"
        verbose_name_plural = "questions fréquentes"
        ordering = ["category", "order"]

    def __str__(self):
        return self.question
