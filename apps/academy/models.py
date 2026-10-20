from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField

from apps.core.models import SluggedModel, TimeStampedModel
from apps.core.storage import private_storage
from apps.core.utils import RandomFilename, age_on
from apps.teams.models import AGE_OF_MAJORITY, Player


class AgeCategory(SluggedModel):
    name = models.CharField("nom", max_length=50, help_text="Ex. U15.")
    min_birth_year = models.PositiveSmallIntegerField("né(e) à partir de")
    max_birth_year = models.PositiveSmallIntegerField("né(e) jusqu'en")
    description = models.TextField("description", blank=True)
    team = models.ForeignKey(
        "teams.Team",
        verbose_name="équipe",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="age_categories",
    )
    order = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "catégorie d'âge"
        verbose_name_plural = "catégories d'âge"
        ordering = ["order", "-max_birth_year"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_birth_year__gte=models.F("min_birth_year")),
                name="academy_agecategory_year_range",
                violation_error_message="L'année de fin doit être postérieure ou égale au début.",
            ),
        ]

    def __str__(self):
        return self.name


class TrainingProgram(SluggedModel):
    slug_source = "title"

    title = models.CharField("titre", max_length=200)
    age_category = models.ForeignKey(
        AgeCategory,
        verbose_name="catégorie d'âge",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="programs",
    )
    body = models.TextField("contenu", blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)
    is_published = models.BooleanField("publié", default=True)

    class Meta:
        verbose_name = "programme de formation"
        verbose_name_plural = "programmes de formation"
        ordering = ["order", "title"]

    def __str__(self):
        return self.title


class AcademyEvent(TimeStampedModel):
    class Kind(models.TextChoices):
        TRAINING = "TRAINING", "Entraînement"
        TRIAL = "TRIAL", "Détection"
        TOURNAMENT = "TOURNAMENT", "Tournoi"
        OPEN_DAY = "OPEN_DAY", "Journée portes ouvertes"

    title = models.CharField("titre", max_length=200)
    kind = models.CharField("type", max_length=10, choices=Kind.choices)
    starts_at = models.DateTimeField("début")
    ends_at = models.DateTimeField("fin", null=True, blank=True)
    location = models.CharField("lieu", max_length=200, blank=True)
    age_category = models.ForeignKey(
        AgeCategory,
        verbose_name="catégorie d'âge",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    description = models.TextField("description", blank=True)
    is_published = models.BooleanField("publié", default=True)

    class Meta:
        verbose_name = "activité du centre"
        verbose_name_plural = "calendrier du centre"
        ordering = ["starts_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__isnull=True)
                | models.Q(ends_at__gt=models.F("starts_at")),
                name="academy_event_ends_after_start",
                violation_error_message="La fin doit suivre le début.",
            ),
        ]

    def __str__(self):
        return self.title


class Application(TimeStampedModel):
    """Candidature au centre de formation. Données personnelles d'enfants : accès
    réservé aux personnes habilitées et suppression à ``retention_until``."""

    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Reçue"
        UNDER_REVIEW = "UNDER_REVIEW", "En cours d'examen"
        TRIAL_INVITED = "TRIAL_INVITED", "Invité(e) à un essai"
        ACCEPTED = "ACCEPTED", "Acceptée"
        REJECTED = "REJECTED", "Refusée"
        WITHDRAWN = "WITHDRAWN", "Retirée"

    class Gender(models.TextChoices):
        MALE = "MALE", "Garçon"
        FEMALE = "FEMALE", "Fille"

    GUARDIAN_FIELDS = ("guardian_name", "guardian_relationship", "guardian_phone")

    reference = models.CharField("référence", max_length=20, unique=True)
    # Candidat
    first_name = models.CharField("prénom", max_length=100)
    last_name = models.CharField("nom", max_length=100)
    birth_date = models.DateField("date de naissance")
    gender = models.CharField("sexe", max_length=6, choices=Gender.choices)
    nationality = CountryField("nationalité", default="CI")
    city = models.CharField("ville", max_length=100)
    email = models.EmailField("e-mail", blank=True)
    phone = PhoneNumberField("téléphone", blank=True)
    # Informations sportives
    age_category = models.ForeignKey(
        AgeCategory,
        verbose_name="catégorie demandée",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
    )
    position = models.CharField("poste", max_length=2, choices=Player.Position.choices, blank=True)
    preferred_foot = models.CharField(
        "pied fort", max_length=5, choices=Player.Foot.choices, blank=True
    )
    current_club = models.CharField("club actuel", max_length=150, blank=True)
    experience = models.TextField("parcours sportif", blank=True)
    # Représentant légal (obligatoire pour un mineur)
    guardian_name = models.CharField("représentant légal", max_length=150, blank=True)
    guardian_relationship = models.CharField("lien de parenté", max_length=50, blank=True)
    guardian_phone = PhoneNumberField("téléphone du représentant", blank=True)
    guardian_email = models.EmailField("e-mail du représentant", blank=True)
    # Consentement
    consent_given = models.BooleanField("consentement au traitement des données", default=False)
    consent_at = models.DateTimeField("consentement donné le", null=True, blank=True)
    # Suivi interne
    status = models.CharField(
        "statut", max_length=15, choices=Status.choices, default=Status.SUBMITTED
    )
    internal_notes = models.TextField("notes internes", blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="examinée par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    retention_until = models.DateField("à supprimer le", null=True, blank=True)

    class Meta:
        verbose_name = "candidature"
        verbose_name_plural = "candidatures"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["retention_until"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(consent_given=True, consent_at__isnull=False),
                name="academy_application_requires_consent",
                violation_error_message="Le consentement au traitement des données est requis.",
            ),
        ]

    def __str__(self):
        return f"{self.reference} — {self.first_name} {self.last_name}"

    @property
    def is_minor(self):
        return self.birth_date is not None and age_on(self.birth_date) < AGE_OF_MAJORITY

    def clean(self):
        super().clean()
        if self.is_minor:
            missing = {
                field: "Obligatoire pour un candidat mineur."
                for field in self.GUARDIAN_FIELDS
                if not getattr(self, field)
            }
            if missing:
                raise ValidationError(missing)


class ApplicationDocument(TimeStampedModel):
    """Pièce jointe d'une candidature, rangée dans le stockage privé (jamais d'URL publique)."""

    class Kind(models.TextChoices):
        BIRTH_CERTIFICATE = "BIRTH_CERTIFICATE", "Extrait de naissance"
        ID_PHOTO = "ID_PHOTO", "Photo d'identité"
        MEDICAL_CERTIFICATE = "MEDICAL_CERTIFICATE", "Certificat médical"
        SCHOOL_REPORT = "SCHOOL_REPORT", "Bulletin scolaire"
        OTHER = "OTHER", "Autre"

    application = models.ForeignKey(
        Application, verbose_name="candidature", on_delete=models.CASCADE, related_name="documents"
    )
    kind = models.CharField("type", max_length=20, choices=Kind.choices)
    file = models.FileField(
        "fichier", storage=private_storage, upload_to=RandomFilename("academy/applications")
    )
    original_name = models.CharField("nom d'origine", max_length=255, blank=True)
    size = models.PositiveIntegerField("taille (octets)", default=0)
    content_type = models.CharField("type de fichier", max_length=100, blank=True)

    class Meta:
        verbose_name = "document de candidature"
        verbose_name_plural = "documents de candidature"
        permissions = [
            ("download_private_document", "Peut télécharger les documents privés des candidats")
        ]
        ordering = ["application", "kind"]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.application.reference}"
