"""Validation des fichiers téléversés (images publiques)."""

from pathlib import PurePath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.defaultfilters import filesizeformat
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
# 40 mégapixels : bien au-delà d'une photo de reportage, en deçà d'une « bombe de
# décompression » (petit fichier qui occuperait des gigaoctets en mémoire une fois ouvert).
MAX_IMAGE_PIXELS = 40_000_000


def validate_image_upload(file):
    """Taille, extension et **contenu réel** d'une image envoyée.

    Le contenu est vérifié par Pillow : un fichier renommé en « .jpg » n'est pas accepté.
    Les fichiers déjà enregistrés (modification d'une fiche) ne sont pas revérifiés.
    """
    if getattr(file, "_committed", False):
        return
    if file.size > settings.MAX_UPLOAD_SIZE:
        raise ValidationError(
            f"Fichier trop lourd ({filesizeformat(file.size)}) : "
            f"{filesizeformat(settings.MAX_UPLOAD_SIZE)} maximum.",
            code="file_too_large",
        )
    if PurePath(file.name).suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            "Format non accepté : JPEG, PNG, WebP ou GIF uniquement.", code="bad_extension"
        )
    try:
        file.seek(0)
        with Image.open(file) as image:
            image_format, (width, height) = image.format, image.size
            if width * height > MAX_IMAGE_PIXELS:
                raise ValidationError(
                    f"Image trop grande ({width} × {height} pixels).", code="too_many_pixels"
                )
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValidationError(
            "Ce fichier n'est pas une image valide.", code="invalid_image"
        ) from error
    finally:
        file.seek(0)
    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError(
            "Format non accepté : JPEG, PNG, WebP ou GIF uniquement.", code="bad_format"
        )
