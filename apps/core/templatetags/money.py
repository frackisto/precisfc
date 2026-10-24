from django import template

from apps.core.utils import format_fcfa

register = template.Library()


@register.filter
def fcfa(value):
    """Montant en francs CFA : « 15 000 FCFA »."""
    return format_fcfa(value)


@register.filter
def thousands(value):
    """Nombre groupé par milliers, sans unité : « 1 250 »."""
    return format_fcfa(value, with_unit=False)
