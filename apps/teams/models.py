from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django_countries.fields import CountryField

from apps.core.models import SluggedModel, TimeStampedModel
from apps.core.utils import age_on, years_ago

AGE_OF_MAJORITY = 18


class Team(SluggedModel):
    class Category(models.TextChoices):
        FIRST = "FIRST", "Équipe première"
        WOMEN = "WOMEN", "Équipe féminine"
        RESERVE = "RESERVE", "Réserve"
        U21 = "U21", "U21"
        U18 = "U18", "U18"
        U17 = "U17", "U17"
        U15 = "U15", "U15"
        U13 = "U13", "U13"
        ACADEMY = "ACADEMY", "Académie"

    class Gender(models.TextChoices):
        MALE = "MALE", "Masculin"
        FEMALE = "FEMALE", "Féminin"
        MIXED = "MIXED", "Mixte"

    name = models.CharField("nom", max_length=100)
    category = models.CharField("catégorie", max_length=10, choices=Category.choices)
    gender = models.CharField("genre", max_length=10, choices=Gender.choices, default=Gender.MALE)
    description = models.TextField("présentation", blank=True)
    image = models.ImageField("photo d'équipe", upload_to="teams/", blank=True)
    season = models.ForeignKey(
        "competitions.Season",
        verbose_name="saison",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teams",
    )
    head_coach = models.ForeignKey(
        "Staff",
        verbose_name="entraîneur principal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coached_teams",
    )
    order = models.PositiveSmallIntegerField("ordre", default=0)
    is_published = models.BooleanField("publiée", default=True)

    class Meta:
        verbose_name = "équipe"
        verbose_name_plural = "équipes"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("teams:detail", args=[self.slug])


class PlayerQuerySet(models.QuerySet):
    def public(self):
        """Joueurs visibles sur le site public.

        Un joueur mineur n'apparaît qu'avec le consentement de son représentant légal.
        Sans date de naissance connue, le joueur est traité comme majeur : la date est
        obligatoire dans les formulaires de saisie des équipes de jeunes.
        """
        majority_cutoff = years_ago(AGE_OF_MAJORITY)
        return self.filter(is_published=True).filter(
            models.Q(publication_consent=True)
            | models.Q(birth_date__isnull=True)
            | models.Q(birth_date__lte=majority_cutoff)
        )


class Player(SluggedModel):
    class Position(models.TextChoices):
        GK = "GK", "Gardien"
        DF = "DF", "Défenseur"
        MF = "MF", "Milieu"
        FW = "FW", "Attaquant"

    class Foot(models.TextChoices):
        RIGHT = "RIGHT", "Droit"
        LEFT = "LEFT", "Gauche"
        BOTH = "BOTH", "Les deux"

    slug_source = "full_name"

    team = models.ForeignKey(
        Team, verbose_name="équipe", on_delete=models.PROTECT, related_name="players"
    )
    first_name = models.CharField("prénom", max_length=100)
    last_name = models.CharField("nom", max_length=100)
    photo = models.ImageField("photo", upload_to="players/", blank=True)
    shirt_number = models.PositiveSmallIntegerField(
        "numéro", null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(99)]
    )
    position = models.CharField("poste", max_length=2, choices=Position.choices)
    detailed_position = models.CharField("poste précis", max_length=50, blank=True)
    nationality = CountryField("nationalité", blank=True)
    birth_date = models.DateField("date de naissance", null=True, blank=True)
    height_cm = models.PositiveSmallIntegerField(
        "taille (cm)",
        null=True,
        blank=True,
        validators=[MinValueValidator(100), MaxValueValidator(230)],
    )
    weight_kg = models.PositiveSmallIntegerField(
        "poids (kg)",
        null=True,
        blank=True,
        validators=[MinValueValidator(30), MaxValueValidator(150)],
    )
    preferred_foot = models.CharField("pied fort", max_length=5, choices=Foot.choices, blank=True)
    bio = models.TextField("biographie", blank=True)
    joined_on = models.DateField("arrivé au club le", null=True, blank=True)
    is_featured = models.BooleanField("joueur vedette", default=False)
    is_published = models.BooleanField("publié", default=True)
    show_birth_date = models.BooleanField("afficher la date de naissance", default=False)
    show_physical = models.BooleanField("afficher taille et poids", default=True)
    publication_consent = models.BooleanField(
        "consentement à la publication",
        default=False,
        help_text="Obligatoire pour afficher un joueur mineur : accord du représentant légal.",
    )
    consent_by = models.CharField("consentement donné par", max_length=150, blank=True)
    consent_date = models.DateField("date du consentement", null=True, blank=True)

    objects = PlayerQuerySet.as_manager()

    class Meta:
        verbose_name = "joueur"
        verbose_name_plural = "joueurs"
        ordering = ["team", "shirt_number", "last_name"]
        constraints = [
            # Plusieurs joueurs sans numéro (NULL) restent possibles.
            models.UniqueConstraint(
                fields=["team", "shirt_number"],
                name="teams_player_unique_shirt_number",
                violation_error_message="Ce numéro est déjà porté dans cette équipe.",
            ),
        ]
        indexes = [models.Index(fields=["is_published", "position"])]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_minor(self):
        return self.birth_date is not None and age_on(self.birth_date) < AGE_OF_MAJORITY

    @property
    def is_public(self):
        """Même règle que ``Player.objects.public()``, pour un joueur déjà chargé."""
        return self.is_published and (self.publication_consent or not self.is_minor)

    def get_absolute_url(self):
        return reverse("teams:player", args=[self.slug])

    @property
    def public_birth_date_label(self):
        """Date de naissance affichable : année seule pour un mineur, rien si masquée."""
        if self.birth_date is None or not (self.show_birth_date or self.is_minor):
            return ""
        if self.is_minor:
            return str(self.birth_date.year)
        return self.birth_date.strftime("%d/%m/%Y")


class PlayerPhoto(TimeStampedModel):
    player = models.ForeignKey(
        Player, verbose_name="joueur", on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField("image", upload_to="players/photos/")
    caption = models.CharField("légende", max_length=200, blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "photo de joueur"
        verbose_name_plural = "photos de joueur"
        ordering = ["order", "pk"]

    def __str__(self):
        return self.caption or f"Photo de {self.player}"


class Staff(SluggedModel):
    class Role(models.TextChoices):
        HEAD_COACH = "HEAD_COACH", "Entraîneur principal"
        ASSISTANT = "ASSISTANT", "Entraîneur adjoint"
        GK_COACH = "GK_COACH", "Entraîneur des gardiens"
        FITNESS = "FITNESS", "Préparateur physique"
        DOCTOR = "DOCTOR", "Médecin"
        PHYSIO = "PHYSIO", "Kinésithérapeute"
        ANALYST = "ANALYST", "Analyste vidéo"
        ACADEMY_MANAGER = "ACADEMY_MANAGER", "Responsable du centre de formation"
        TEAM_MANAGER = "TEAM_MANAGER", "Intendant"
        OTHER = "OTHER", "Autre"

    slug_source = "full_name"

    team = models.ForeignKey(
        Team,
        verbose_name="équipe",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff",
    )
    first_name = models.CharField("prénom", max_length=100)
    last_name = models.CharField("nom", max_length=100)
    photo = models.ImageField("photo", upload_to="staff/", blank=True)
    role = models.CharField("fonction", max_length=20, choices=Role.choices)
    bio = models.TextField("biographie", blank=True)
    nationality = CountryField("nationalité", blank=True)
    joined_on = models.DateField("arrivé au club le", null=True, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="compte utilisateur",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_profile",
    )
    order = models.PositiveSmallIntegerField("ordre", default=0)
    is_published = models.BooleanField("publié", default=True)

    class Meta:
        verbose_name = "membre du staff"
        verbose_name_plural = "staff technique"
        ordering = ["order", "last_name"]

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
