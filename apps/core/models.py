from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from .fields import URLField
from .utils import unique_slug

hex_color_validator = RegexValidator(
    r"^#[0-9A-Fa-f]{6}$", "Couleur au format hexadécimal, par exemple #0B1F3A."
)


class TimeStampedModel(models.Model):
    """Base commune : dates de création et de dernière modification."""

    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        abstract = True


class SluggedModel(TimeStampedModel):
    """Objet public adressé par un slug unique, généré au premier enregistrement.

    ``slug_source`` désigne l'attribut (champ ou propriété) dont le slug est dérivé.
    Un slug déjà défini n'est jamais modifié, pour ne pas casser les liens existants.
    """

    slug = models.SlugField("slug", max_length=220, unique=True, blank=True)

    slug_source = "name"

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, str(getattr(self, self.slug_source)))
        super().save(*args, **kwargs)


class SEOFields(models.Model):
    """Métadonnées de référencement ; vides, elles sont déduites du contenu."""

    meta_title = models.CharField("titre SEO", max_length=70, blank=True)
    meta_description = models.CharField("description SEO", max_length=160, blank=True)
    og_image = models.ImageField("image de partage", upload_to="seo/", blank=True)

    class Meta:
        abstract = True


class SingletonModel(TimeStampedModel):
    """Modèle à une seule ligne (clé primaire forcée à 1)."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        if self._state.adding:
            # Nouvelle instance alors que la ligne existe : on la met à jour en gardant
            # sa date de création (sinon Django l'écrirait à NULL).
            created_at = type(self).objects.filter(pk=1).values_list("created_at", flat=True)
            if created_at:
                self.created_at = created_at[0]
                self._state.adding = False
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ScheduledJobRun(models.Model):
    """État d'une tâche périodique exécutée par le cron (voir core/scheduling.py)."""

    class Status(models.TextChoices):
        NEVER = "", "Jamais exécutée"
        SUCCESS = "success", "Réussie"
        FAILED = "failed", "Échouée"

    name = models.CharField("tâche", max_length=150, unique=True)
    last_started_at = models.DateTimeField("dernier démarrage", null=True, blank=True)
    last_finished_at = models.DateTimeField("dernière fin", null=True, blank=True)
    last_status = models.CharField(
        "dernier statut", max_length=10, choices=Status.choices, blank=True, default=Status.NEVER
    )
    last_error = models.TextField("dernière erreur", blank=True)
    # Verrou à durée limitée : empêche deux exécutions simultanées de la même tâche.
    locked_until = models.DateTimeField("verrouillée jusqu'à", null=True, blank=True)

    class Meta:
        verbose_name = "exécution de tâche planifiée"
        verbose_name_plural = "exécutions de tâches planifiées"
        ordering = ["name"]

    def __str__(self):
        return self.name


# --- Infrastructures ------------------------------------------------------------


class Facility(SluggedModel):
    class Kind(models.TextChoices):
        STADIUM = "STADIUM", "Stade"
        TRAINING_CENTRE = "TRAINING_CENTRE", "Centre d'entraînement"
        ACADEMY = "ACADEMY", "Centre de formation"
        OFFICE = "OFFICE", "Siège"

    name = models.CharField("nom", max_length=150)
    kind = models.CharField("type", max_length=20, choices=Kind.choices)
    description = models.TextField("description", blank=True)
    capacity = models.PositiveIntegerField("capacité", null=True, blank=True)
    address = models.CharField("adresse", max_length=255, blank=True)
    lat = models.DecimalField("latitude", max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField("longitude", max_digits=9, decimal_places=6, null=True, blank=True)
    cover = models.ImageField("image principale", upload_to="facilities/", blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)
    is_published = models.BooleanField("publiée", default=True)

    class Meta:
        verbose_name = "infrastructure"
        verbose_name_plural = "infrastructures"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class FacilityPhoto(TimeStampedModel):
    facility = models.ForeignKey(
        Facility, verbose_name="infrastructure", on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField("image", upload_to="facilities/photos/")
    caption = models.CharField("légende", max_length=200, blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "photo d'infrastructure"
        verbose_name_plural = "photos d'infrastructure"
        ordering = ["order", "pk"]

    def __str__(self):
        return self.caption or f"Photo de {self.facility}"


# --- Paramètres du club -----------------------------------------------------------


class ClubSettings(SingletonModel):
    """Paramètres globaux du site, modifiables dans l'administration."""

    name = models.CharField("nom du club", max_length=100, default="Precis FC")
    short_name = models.CharField("nom court", max_length=30, default="Precis FC")
    slogan = models.CharField("slogan", max_length=200, blank=True)
    logo = models.ImageField("logo", upload_to="club/", blank=True)
    logo_dark = models.ImageField("logo pour fond sombre", upload_to="club/", blank=True)
    favicon = models.ImageField("favicon", upload_to="club/", blank=True)
    color_primary = models.CharField(
        "couleur principale", max_length=7, default="#0B1F3A", validators=[hex_color_validator]
    )
    color_secondary = models.CharField(
        "couleur secondaire", max_length=7, default="#C9A227", validators=[hex_color_validator]
    )
    color_light = models.CharField(
        "couleur claire", max_length=7, default="#F2F4F7", validators=[hex_color_validator]
    )
    founded_year = models.PositiveSmallIntegerField(
        "année de fondation",
        null=True,
        blank=True,
        validators=[MinValueValidator(1850), MaxValueValidator(2100)],
    )
    home_stadium = models.ForeignKey(
        Facility,
        verbose_name="stade",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    address = models.CharField("adresse", max_length=255, blank=True)
    phone = models.CharField("téléphone", max_length=30, blank=True)
    email = models.EmailField("e-mail", blank=True)
    map_lat = models.DecimalField(
        "latitude (carte)", max_digits=9, decimal_places=6, null=True, blank=True
    )
    map_lng = models.DecimalField(
        "longitude (carte)", max_digits=9, decimal_places=6, null=True, blank=True
    )
    facebook_url = URLField("Facebook", blank=True)
    x_url = URLField("X (Twitter)", blank=True)
    instagram_url = URLField("Instagram", blank=True)
    youtube_url = URLField("YouTube", blank=True)
    tiktok_url = URLField("TikTok", blank=True)
    linkedin_url = URLField("LinkedIn", blank=True)
    currency = models.CharField("devise", max_length=3, default="XOF", editable=False)
    default_meta_description = models.CharField(
        "description SEO par défaut", max_length=160, blank=True
    )
    default_og_image = models.ImageField(
        "image de partage par défaut", upload_to="seo/", blank=True
    )
    about_short = models.TextField("présentation courte", blank=True)

    class Meta:
        verbose_name = "paramètres du club"
        verbose_name_plural = "paramètres du club"
        # Droits transverses, rattachés aux paramètres faute de modèle « tableau de bord ».
        permissions = [
            ("view_dashboard", "Peut accéder au tableau de bord"),
            ("view_financial_reports", "Peut consulter les indicateurs financiers"),
        ]

    def __str__(self):
        return "Paramètres du club"


class HeroSlide(TimeStampedModel):
    """Bannière défilante de la page d'accueil."""

    title = models.CharField("titre", max_length=150)
    subtitle = models.CharField("sous-titre", max_length=255, blank=True)
    image = models.ImageField("image", upload_to="hero/")
    cta_label = models.CharField("texte du bouton", max_length=40, blank=True)
    cta_url = models.CharField("lien du bouton", max_length=255, blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)
    is_active = models.BooleanField("active", default=True)
    starts_at = models.DateTimeField("début d'affichage", null=True, blank=True)
    ends_at = models.DateTimeField("fin d'affichage", null=True, blank=True)

    class Meta:
        verbose_name = "bannière d'accueil"
        verbose_name_plural = "bannières d'accueil"
        ordering = ["order", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(starts_at__isnull=True)
                | models.Q(ends_at__isnull=True)
                | models.Q(ends_at__gt=models.F("starts_at")),
                name="core_heroslide_ends_after_start",
                violation_error_message="La fin d'affichage doit suivre le début.",
            ),
        ]

    def __str__(self):
        return self.title


# --- Pages institutionnelles --------------------------------------------------


class Page(SluggedModel, SEOFields):
    class Section(models.TextChoices):
        HISTORY = "HISTORY", "Histoire"
        MISSION = "MISSION", "Mission, vision et valeurs"
        IDENTITY = "IDENTITY", "Identité visuelle"
        SPORTING_DIRECTION = "SPORTING_DIRECTION", "Direction sportive"
        TRAINING_CENTRE = "TRAINING_CENTRE", "Centre de formation"
        OTHER = "OTHER", "Autre"

    slug_source = "title"

    section = models.CharField("rubrique", max_length=20, choices=Section.choices)
    title = models.CharField("titre", max_length=200)
    # HTML assaini à l'enregistrement (éditeur riche ajouté à l'étape 9).
    body = models.TextField("contenu", blank=True)
    cover = models.ImageField("image de couverture", upload_to="pages/", blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)
    is_published = models.BooleanField("publiée", default=False)

    class Meta:
        verbose_name = "page"
        verbose_name_plural = "pages"
        ordering = ["section", "order", "title"]

    def __str__(self):
        return self.title


class Value(TimeStampedModel):
    title = models.CharField("titre", max_length=100)
    description = models.TextField("description", blank=True)
    icon = models.CharField(
        "icône", max_length=50, blank=True, help_text="Nom d'une icône Bootstrap, ex. trophy."
    )
    order = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "valeur"
        verbose_name_plural = "valeurs"
        ordering = ["order", "title"]

    def __str__(self):
        return self.title


# --- Palmarès et histoire -------------------------------------------------------


class Trophy(TimeStampedModel):
    name = models.CharField("trophée", max_length=150)
    competition_name = models.CharField("compétition", max_length=150, blank=True)
    category = models.CharField(
        "catégorie", max_length=50, blank=True, help_text="Ex. équipe première, féminines, U17."
    )
    image = models.ImageField("image", upload_to="trophies/", blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "trophée"
        verbose_name_plural = "trophées"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class TrophyWin(TimeStampedModel):
    trophy = models.ForeignKey(
        Trophy, verbose_name="trophée", on_delete=models.CASCADE, related_name="wins"
    )
    season_label = models.CharField("saison", max_length=20, blank=True)
    year = models.PositiveSmallIntegerField(
        "année", validators=[MinValueValidator(1850), MaxValueValidator(2100)]
    )
    notes = models.CharField("remarques", max_length=255, blank=True)

    class Meta:
        verbose_name = "titre remporté"
        verbose_name_plural = "titres remportés"
        ordering = ["-year"]

    def __str__(self):
        return f"{self.trophy} {self.season_label or self.year}"


class President(TimeStampedModel):
    full_name = models.CharField("nom complet", max_length=150)
    photo = models.ImageField("photo", upload_to="presidents/", blank=True)
    start_year = models.PositiveSmallIntegerField("début du mandat")
    end_year = models.PositiveSmallIntegerField("fin du mandat", null=True, blank=True)
    bio = models.TextField("biographie", blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "président"
        verbose_name_plural = "présidents successifs"
        ordering = ["order", "-start_year"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_year__isnull=True)
                | models.Q(end_year__gte=models.F("start_year")),
                name="core_president_end_after_start",
                violation_error_message="La fin du mandat ne peut précéder son début.",
            ),
        ]

    def __str__(self):
        return self.full_name


class OrgMember(TimeStampedModel):
    """Membre de l'organigramme."""

    class Department(models.TextChoices):
        DIRECTION = "DIRECTION", "Direction"
        ADMINISTRATION = "ADMINISTRATION", "Administration"
        SPORTING = "SPORTING", "Sportive"
        MEDICAL = "MEDICAL", "Médical"
        COMMUNICATION = "COMMUNICATION", "Communication"
        COMMERCIAL = "COMMERCIAL", "Commercial"
        ACADEMY = "ACADEMY", "Centre de formation"

    full_name = models.CharField("nom complet", max_length=150)
    photo = models.ImageField("photo", upload_to="organisation/", blank=True)
    role_title = models.CharField("fonction", max_length=150)
    department = models.CharField("département", max_length=20, choices=Department.choices)
    bio = models.TextField("biographie", blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)
    is_published = models.BooleanField("publié", default=True)

    class Meta:
        verbose_name = "membre de l'organigramme"
        verbose_name_plural = "organigramme"
        ordering = ["department", "order", "full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.role_title})"
