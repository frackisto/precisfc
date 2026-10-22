import json

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# Mêmes échappements que le filtre json_script de Django : aucun contenu saisi dans
# l'administration ne peut fermer la balise <script> ni injecter du HTML.
_BACKSLASH = chr(92)
_ESCAPES = {ord(char): f"{_BACKSLASH}u{ord(char):04X}" for char in "<>&"}


@register.simple_tag
def jsonld(data):
    """Données structurées Schema.org : <script type="application/ld+json">.

    Un bloc de données, jamais exécuté par le navigateur.
    """
    payload = json.dumps(data, ensure_ascii=False).translate(_ESCAPES)
    return format_html('<script type="application/ld+json">{}</script>', mark_safe(payload))  # noqa: S308
