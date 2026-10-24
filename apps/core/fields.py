"""Champs de modèle propres au projet."""

from django.db import models

from .validators import validate_image_upload


class URLField(models.URLField):
    """Adresse web : « facebook.com/precisfc » est complétée en https:// (et non http://).

    Reprend dès maintenant le comportement par défaut de Django 6.
    """

    def formfield(self, **kwargs):
        return super().formfield(**{"assume_scheme": "https", **kwargs})


class ImageField(models.ImageField):
    """Image publique, validée à l'envoi : poids, format et contenu réel (Pillow).

    Se présente aux migrations comme un ``ImageField`` ordinaire : aucune migration.
    """

    default_validators = [validate_image_upload]

    def deconstruct(self):
        name, _path, args, kwargs = super().deconstruct()
        return name, "django.db.models.ImageField", args, kwargs
