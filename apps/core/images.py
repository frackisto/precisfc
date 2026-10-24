"""Déclinaisons d'images (django-imagekit), toutes en WebP.

Générées au premier affichage puis conservées dans MEDIA_ROOT/CACHE : les pages
chargent une image à la bonne taille, bien plus légère que l'original.
"""

from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit

WEBP = {"format": "WEBP", "options": {"quality": 80}}


def thumbnail(source, width=400, height=300):
    """Vignette recadrée à la taille exacte (grilles, cartes)."""
    return ImageSpecField(source=source, processors=[ResizeToFill(width, height)], **WEBP)


def resized(source, width, height=None):
    """Image entière réduite, sans recadrage ni agrandissement."""
    return ImageSpecField(
        source=source, processors=[ResizeToFit(width, height or width, upscale=False)], **WEBP
    )


def delete_with_versions(instance, field_name: str, *spec_names: str) -> None:
    """Supprime une image et ses déclinaisons déjà générées.

    Les déclinaisons sont nommées d'après l'original : sans ce ménage, une nouvelle image
    enregistrée plus tard sous le même nom afficherait les anciennes versions en cache.
    """
    source = getattr(instance, field_name)
    if not source:
        return
    for spec_name in spec_names:
        version = getattr(instance, spec_name)
        if version.storage.exists(version.name):
            version.storage.delete(version.name)
    source.delete(save=False)
