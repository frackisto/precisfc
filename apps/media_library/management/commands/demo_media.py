"""Albums photo et vidéos de démonstration, pour voir la médiathèque avec du contenu.

    python manage.py demo_media           # crée (ou recrée) la démonstration
    python manage.py demo_media --delete  # la supprime, images comprises

Deux albums de photos provisoires (générées, 1600 × 1200, pour voir les déclinaisons
WebP et la visionneuse) et trois vidéos réelles en licence libre de la Blender
Foundation (*Big Buck Bunny*, *Sintel*), sur YouTube et Vimeo.

Tout ce qui est créé a un slug commençant par « demo- » : rien d'autre n'est touché.
"""

import colorsys
from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from apps.core.images import delete_with_versions
from apps.core.management.commands.demo_banners import _text
from apps.media_library.models import Album, Photo, Video

PREFIX = "demo-"
WIDTH, HEIGHT = 1600, 1200
ALBUMS = [
    # (slug, titre, type, nombre de photos, il y a n jours)
    ("demo-victoire-a-domicile", "Victoire à domicile (démo)", "MATCH", 8, 3),
    ("demo-seance-d-entrainement", "Séance d'entraînement (démo)", "TRAINING", 6, 10),
]
VIDEOS = [
    # (slug, titre, type, plateforme, identifiant) : films libres de la Blender Foundation
    ("demo-big-buck-bunny-youtube", "Big Buck Bunny (démo)", "EVENT", "YOUTUBE", "aqz-KE-bpKQ"),
    ("demo-sintel", "Sintel (démo)", "EVENT", "YOUTUBE", "eRsGyueVLvQ"),
    ("demo-big-buck-bunny-vimeo", "Big Buck Bunny (démo Vimeo)", "EVENT", "VIMEO", "1084537"),
]  # fmt: skip


def placeholder_photo(number: int, total: int, title: str) -> bytes:
    """Photo provisoire : dégradé de couleur différent pour chaque numéro."""
    hue = number / max(total, 1)
    top = tuple(round(value * 255) for value in colorsys.hsv_to_rgb(hue, 0.55, 0.55))
    bottom = tuple(round(value * 255) for value in colorsys.hsv_to_rgb(hue, 0.45, 0.85))
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        draw.line(
            [(0, y), (WIDTH, y)],
            fill=tuple(round(a + (b - a) * ratio) for a, b in zip(top, bottom, strict=True)),
        )
    center = (WIDTH // 2, HEIGHT // 2)
    _text(draw, center, f"Photo {number}", 140, fill=(255, 255, 255), anchor="mm")
    _text(draw, (center[0], center[1] + 120), title, 48, fill=(255, 255, 255), anchor="mm")
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


class Command(BaseCommand):
    help = "Crée (ou supprime avec --delete) des albums photo et des vidéos de démonstration."

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true", help="Supprime la démonstration.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Autorise l'exécution hors développement (le contenu serait public).",
        )

    def handle(self, *args, delete=False, force=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError(
                "Commande de démonstration : réservée au développement (DEBUG). "
                "Ajouter --force pour l'exécuter quand même."
            )
        self.delete_demo()
        if delete:
            self.stdout.write(self.style.SUCCESS("Médias de démonstration supprimés."))
            return
        self.create_demo()
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(ALBUMS)} albums et {len(VIDEOS)} vidéos de démonstration prêts : /medias/"
            )
        )

    @transaction.atomic
    def delete_demo(self):
        for album in Album.objects.filter(slug__startswith=PREFIX):
            for photo in album.photos.all():
                delete_with_versions(photo, "image", "thumb", "medium", "large")
            delete_with_versions(album, "cover", "cover_thumb")
            album.delete()
        Video.objects.filter(slug__startswith=PREFIX).delete()

    @transaction.atomic
    def create_demo(self):
        now = timezone.now()
        for slug, title, kind, count, days_ago in ALBUMS:
            album = Album.objects.create(
                slug=slug,
                title=title,
                kind=kind,
                event_date=(now - timedelta(days=days_ago)).date(),
                is_published=True,
                published_at=now - timedelta(days=days_ago),
            )
            for number in range(1, count + 1):
                content = ContentFile(placeholder_photo(number, count, title))
                photo = Photo(
                    album=album,
                    caption=f"Photo {number} — {title}",
                    alt_text=f"Photo de démonstration numéro {number}",
                    credit="Precis FC (démo)",
                    order=number,
                )
                photo.image.save(f"{slug}-{number}.jpg", content, save=True)
                if number == 1:
                    album.cover.save(f"{slug}-couverture.jpg", content, save=True)
            self.stdout.write(f"Album : {title} ({count} photos)")
        for days_ago, (slug, title, kind, provider, video_id) in enumerate(VIDEOS):
            Video.objects.create(
                slug=slug,
                title=title,
                kind=kind,
                provider=provider,
                video_id=video_id,
                description="Film d'animation libre de la Blender Foundation (démonstration).",
                is_published=True,
                published_at=now - timedelta(days=days_ago),
            )
            self.stdout.write(f"Vidéo : {title}")
