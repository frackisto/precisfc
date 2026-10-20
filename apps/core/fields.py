"""Champs de modèle propres au projet."""

from django.db import models


class URLField(models.URLField):
    """Adresse web : « facebook.com/precisfc » est complétée en https:// (et non http://).

    Reprend dès maintenant le comportement par défaut de Django 6.
    """

    def formfield(self, **kwargs):
        return super().formfield(**{"assume_scheme": "https", **kwargs})
