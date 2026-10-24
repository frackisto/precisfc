from django import template

from apps.core.html import render_rich_text

register = template.Library()


@register.filter
def rich_text(value):
    """Contenu de l'éditeur, assaini une seconde fois à l'affichage."""
    return render_rich_text(value)
