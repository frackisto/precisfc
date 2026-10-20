import uuid

from django.conf import settings
from django.db import models

from apps.core.models import SEOFields, SluggedModel


class Category(SluggedModel):
    name = models.CharField("nom", max_length=100, unique=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "catégorie"
        verbose_name_plural = "catégories"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Tag(SluggedModel):
    name = models.CharField("nom", max_length=60, unique=True)

    class Meta:
        verbose_name = "mot-clé"
        verbose_name_plural = "mots-clés"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Article(SluggedModel, SEOFields):
    class Kind(models.TextChoices):
        NEWS = "NEWS", "Actualité"
        OFFICIAL = "OFFICIAL", "Communiqué officiel"
        MATCH_PREVIEW = "MATCH_PREVIEW", "Avant-match"
        MATCH_REPORT = "MATCH_REPORT", "Compte rendu de match"
        INTERVIEW = "INTERVIEW", "Interview"
        TRANSFER = "TRANSFER", "Transfert"
        ACADEMY = "ACADEMY", "Centre de formation"
        PARTNER = "PARTNER", "Partenaires"
        EVENT = "EVENT", "Événement"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        IN_REVIEW = "IN_REVIEW", "En relecture"
        SCHEDULED = "SCHEDULED", "Programmé"
        PUBLISHED = "PUBLISHED", "Publié"
        ARCHIVED = "ARCHIVED", "Archivé"

    slug_source = "title"

    kind = models.CharField("type", max_length=15, choices=Kind.choices, default=Kind.NEWS)
    title = models.CharField("titre", max_length=200)
    excerpt = models.CharField("chapeau", max_length=300, blank=True)
    # HTML assaini à l'enregistrement (éditeur riche ajouté à l'étape 9).
    body = models.TextField("contenu", blank=True)
    cover_image = models.ImageField("image principale", upload_to="news/%Y/%m/", blank=True)
    cover_alt = models.CharField("texte alternatif de l'image", max_length=255, blank=True)
    gallery = models.ForeignKey(
        "media_library.Album",
        verbose_name="galerie",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )
    category = models.ForeignKey(
        Category,
        verbose_name="catégorie",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="articles",
    )
    tags = models.ManyToManyField(
        Tag, verbose_name="mots-clés", blank=True, related_name="articles"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="auteur",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )
    status = models.CharField("statut", max_length=10, choices=Status.choices, default=Status.DRAFT)
    publish_at = models.DateTimeField("date de publication", null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="relu par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    reviewed_at = models.DateTimeField("relu le", null=True, blank=True)
    review_note = models.TextField("remarques de relecture", blank=True)
    related_match = models.ForeignKey(
        "matches.Match",
        verbose_name="match lié",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )
    related_players = models.ManyToManyField(
        "teams.Player", verbose_name="joueurs cités", blank=True, related_name="articles"
    )
    is_featured = models.BooleanField("à la une", default=False)
    # Lien de prévisualisation d'un brouillon, imprévisible et renouvelable.
    preview_token = models.UUIDField("jeton de prévisualisation", default=uuid.uuid4, unique=True)

    class Meta:
        verbose_name = "article"
        verbose_name_plural = "articles"
        ordering = ["-publish_at", "-pk"]
        indexes = [models.Index(fields=["status", "publish_at"])]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(status__in=["SCHEDULED", "PUBLISHED"])
                | models.Q(publish_at__isnull=False),
                name="news_article_published_has_date",
                violation_error_message="Un article programmé ou publié doit avoir une date.",
            ),
        ]

    def __str__(self):
        return self.title
