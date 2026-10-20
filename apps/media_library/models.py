import re

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import SluggedModel, TimeStampedModel


class MediaKind(models.TextChoices):
    MATCH = "MATCH", "Match"
    SEASON = "SEASON", "Saison"
    TRAINING = "TRAINING", "Entraînement"
    PLAYERS = "PLAYERS", "Joueurs"
    EVENT = "EVENT", "Événement"
    ACADEMY = "ACADEMY", "Centre de formation"


class Album(SluggedModel):
    slug_source = "title"

    title = models.CharField("titre", max_length=200)
    kind = models.CharField("type", max_length=10, choices=MediaKind.choices)
    season = models.ForeignKey(
        "competitions.Season",
        verbose_name="saison",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="albums",
    )
    match = models.ForeignKey(
        "matches.Match",
        verbose_name="match",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="albums",
    )
    cover = models.ImageField("couverture", upload_to="albums/covers/", blank=True)
    event_date = models.DateField("date", null=True, blank=True)
    is_published = models.BooleanField("publié", default=False)
    published_at = models.DateTimeField("publié le", null=True, blank=True)

    class Meta:
        verbose_name = "album photo"
        verbose_name_plural = "albums photo"
        ordering = ["-event_date", "-pk"]
        indexes = [models.Index(fields=["is_published", "published_at"])]

    def __str__(self):
        return self.title


class Photo(TimeStampedModel):
    """Photo d'un album ; les déclinaisons WebP (vignette, moyenne, grande) sont
    générées par django-imagekit à partir de ``image`` (étape 9)."""

    album = models.ForeignKey(
        Album, verbose_name="album", on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField(
        "image", upload_to="albums/%Y/%m/", width_field="width", height_field="height"
    )
    caption = models.CharField("légende", max_length=255, blank=True)
    alt_text = models.CharField(
        "texte alternatif",
        max_length=255,
        blank=True,
        help_text="Description pour l'accessibilité.",
    )
    credit = models.CharField("crédit photo", max_length=100, blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)
    width = models.PositiveIntegerField("largeur", null=True, blank=True, editable=False)
    height = models.PositiveIntegerField("hauteur", null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "photo"
        verbose_name_plural = "photos"
        ordering = ["album", "order", "pk"]

    def __str__(self):
        return self.caption or f"Photo {self.pk} — {self.album}"


class Video(SluggedModel):
    class Provider(models.TextChoices):
        YOUTUBE = "YOUTUBE", "YouTube"
        VIMEO = "VIMEO", "Vimeo"
        DAILYMOTION = "DAILYMOTION", "Dailymotion"

    # Identifiant attendu pour chaque plateforme : seul ce code est stocké, jamais une
    # URL ou un code HTML d'intégration (aucune injection possible dans la page).
    VIDEO_ID_PATTERNS = {
        Provider.YOUTUBE: re.compile(r"^[A-Za-z0-9_-]{11}$"),
        Provider.VIMEO: re.compile(r"^[0-9]{6,12}$"),
        Provider.DAILYMOTION: re.compile(r"^x[a-z0-9]{5,10}$"),
    }
    EMBED_URLS = {
        Provider.YOUTUBE: "https://www.youtube-nocookie.com/embed/{}",
        Provider.VIMEO: "https://player.vimeo.com/video/{}",
        Provider.DAILYMOTION: "https://www.dailymotion.com/embed/video/{}",
    }

    slug_source = "title"

    title = models.CharField("titre", max_length=200)
    kind = models.CharField("type", max_length=10, choices=MediaKind.choices)
    provider = models.CharField("plateforme", max_length=12, choices=Provider.choices)
    video_id = models.CharField("identifiant de la vidéo", max_length=20)
    thumbnail = models.ImageField("vignette", upload_to="videos/", blank=True)
    description = models.TextField("description", blank=True)
    match = models.ForeignKey(
        "matches.Match",
        verbose_name="match",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="videos",
    )
    season = models.ForeignKey(
        "competitions.Season",
        verbose_name="saison",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="videos",
    )
    published_at = models.DateTimeField("publiée le", null=True, blank=True)
    is_published = models.BooleanField("publiée", default=False)

    class Meta:
        verbose_name = "vidéo"
        verbose_name_plural = "vidéos"
        ordering = ["-published_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "video_id"],
                name="media_library_video_unique",
                violation_error_message="Cette vidéo est déjà enregistrée.",
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        pattern = self.VIDEO_ID_PATTERNS.get(self.provider)
        if pattern and not pattern.fullmatch(self.video_id or ""):
            raise ValidationError(
                {
                    "video_id": f"Identifiant {self.get_provider_display()} invalide : "
                    "saisir uniquement le code de la vidéo, pas l'adresse complète."
                }
            )

    @property
    def embed_url(self):
        return self.EMBED_URLS[self.provider].format(self.video_id)
