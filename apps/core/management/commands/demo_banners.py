"""Bannières de démonstration pour la page d'accueil (images provisoires générées).

    python manage.py demo_banners           # crée ou met à jour les 4 bannières
    python manage.py demo_banners --delete  # les supprime, images comprises

Les images montrent la zone qui reste visible après recadrage : sur ordinateur (bande
horizontale) et sur téléphone (bande verticale). Le sujet de la vraie photo doit se
trouver à leur croisement.
"""

import unicodedata
from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from apps.core.colors import hex_to_rgb, mix
from apps.core.models import ClubSettings, HeroSlide

WIDTH, HEIGHT = 1920, 1080
# Zones visibles d'une image 1920 × 1080 (voir .hero-image dans static/css/site.css) :
# ordinateur 1920 × 560 → bande de 560 px de haut au centre ;
# téléphone 390 × 464 → bande d'environ 908 px de large au centre.
DESKTOP_BAND = (0, 260, WIDTH, 820)
PHONE_BAND = (506, 0, 1414, HEIGHT)
IMAGE_FOLDER = "hero/demo"


def banners():
    now = timezone.now()
    return [
        {
            "title": "Precis FC, la fierté de [ville]",
            "subtitle": "Un club, une famille, une passion depuis [année de fondation].",
            "cta_label": "Découvrir le club",
            "cta_url": reverse("core:club"),
            "order": 0,
        },
        {
            "title": "Tous au stade samedi !",
            "subtitle": "Precis FC – [adversaire], [journée] de [compétition], "
            "coup d'envoi à [heure].",
            "order": 1,
            "starts_at": now,
            "ends_at": now + timedelta(days=5),
        },
        {
            "title": "Le nouveau maillot est arrivé",
            "subtitle": "Portez les couleurs du club, livraison à Abidjan et partout en "
            "Côte d'Ivoire.",
            "order": 2,
            "starts_at": now,
            "ends_at": now + timedelta(weeks=6),
        },
        {
            "title": "Rejoins l'académie Precis FC",
            "subtitle": "Détections [catégories] : inscriptions ouvertes jusqu'au [date].",
            "order": 3,
            "starts_at": now,
            "ends_at": now + timedelta(weeks=6),
        },
    ]


# Polices avec accents (Windows, puis Linux) ; la police intégrée à Pillow n'en a pas.
FONT_CANDIDATES = ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf")


def _font(size):
    """Police et indicateur « accents disponibles »."""
    for name in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size), True
        except OSError:
            continue
    return ImageFont.load_default(size=size), False


def _text(draw, position, text, size, **kwargs):
    font, has_accents = _font(size)
    if not has_accents:  # repli : texte sans accents plutôt que des carrés
        text = unicodedata.normalize("NFKD", text.replace("×", "x"))
        text = text.encode("ascii", "ignore").decode()
    draw.text(position, text, font=font, **kwargs)


def _dashed_rectangle(draw, box, color, width=4, dash=24):
    left, top, right, bottom = box
    for x in range(left, right, dash * 2):
        draw.line([(x, top), (min(x + dash, right), top)], fill=color, width=width)
        draw.line([(x, bottom - 1), (min(x + dash, right), bottom - 1)], fill=color, width=width)
    for y in range(top, bottom, dash * 2):
        draw.line([(left, y), (left, min(y + dash, bottom))], fill=color, width=width)
        draw.line([(right - 1, y), (right - 1, min(y + dash, bottom))], fill=color, width=width)


def placeholder_image(number: int, primary: str, accent: str) -> bytes:
    """Image provisoire 1920 × 1080 aux couleurs du club, avec les zones de recadrage."""
    top, bottom = hex_to_rgb(primary), tuple(min(255, value + 60) for value in hex_to_rgb(primary))
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        draw.line(
            [(0, y), (WIDTH, y)],
            fill=tuple(round(a + (b - a) * ratio) for a, b in zip(top, bottom, strict=True)),
        )
    accent_rgb = hex_to_rgb(accent)
    stripe = hex_to_rgb(mix(primary, accent, 0.3))
    for offset in range(-HEIGHT, WIDTH, 160):  # rayures diagonales discrètes
        draw.line([(offset, HEIGHT), (offset + HEIGHT, 0)], fill=stripe, width=4)

    _dashed_rectangle(draw, DESKTOP_BAND, (255, 255, 255))
    _dashed_rectangle(draw, PHONE_BAND, accent_rgb)
    _text(draw, (24, DESKTOP_BAND[1] + 16), "Visible sur ordinateur", 32, fill=(255, 255, 255))
    _text(draw, (PHONE_BAND[0] + 16, 24), "Visible sur téléphone", 32, fill=accent_rgb)

    center = (WIDTH // 2, HEIGHT // 2)
    _text(draw, center, "IMAGE PROVISOIRE", 110, fill=(255, 255, 255), anchor="mm")
    _text(
        draw,
        (center[0], center[1] + 110),
        f"Bannière {number} · 1920 × 1080 · sujet au centre",
        48,
        fill=accent_rgb,
        anchor="mm",
    )
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=82, optimize=True)
    return buffer.getvalue()


class Command(BaseCommand):
    help = "Crée (ou supprime avec --delete) 4 bannières de démonstration avec images provisoires."

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete", action="store_true", help="Supprime les bannières de démonstration."
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Autorise l'exécution hors développement (elles seraient visibles du public).",
        )

    def handle(self, *args, delete=False, force=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError(
                "Commande de démonstration : réservée au développement (DEBUG). "
                "Ajouter --force pour l'exécuter quand même."
            )
        if delete:
            self._delete()
        else:
            self._create()

    def _demo_slides(self):
        return HeroSlide.objects.filter(image__startswith=f"{IMAGE_FOLDER}/")

    @transaction.atomic
    def _create(self):
        club = ClubSettings.cached()
        for number, values in enumerate(banners(), start=1):
            path = f"{IMAGE_FOLDER}/banniere-{number}.jpg"
            if default_storage.exists(path):
                default_storage.delete(path)
            saved = default_storage.save(
                path,
                ContentFile(placeholder_image(number, club.color_primary, club.color_secondary)),
            )
            defaults = {
                "subtitle": "",
                "cta_label": "",
                "cta_url": "",
                "starts_at": None,
                "ends_at": None,
                "is_active": True,
                **{key: value for key, value in values.items() if key != "title"},
                "image": saved,
            }
            slide, created = HeroSlide.objects.update_or_create(
                title=values["title"], image__startswith=f"{IMAGE_FOLDER}/", defaults=defaults
            )
            self.stdout.write(f"{'Créée' if created else 'Mise à jour'} : {slide.title}")
        self.stdout.write(
            self.style.SUCCESS("4 bannières de démonstration prêtes (voir l'accueil).")
        )

    @transaction.atomic
    def _delete(self):
        slides = list(self._demo_slides())
        for slide in slides:
            if slide.image and default_storage.exists(slide.image.name):
                default_storage.delete(slide.image.name)
            slide.delete()
        self.stdout.write(
            self.style.SUCCESS(f"{len(slides)} bannière(s) de démonstration supprimée(s).")
        )
