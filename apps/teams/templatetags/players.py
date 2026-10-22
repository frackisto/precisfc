from django import template

register = template.Library()

ANONYMOUS = "Joueur du club"


@register.filter
def public_name(player, fallback=""):
    """Nom affichable d'un joueur dans une feuille de match.

    Joueur du club non public (mineur sans consentement, fiche non publiée) : nom masqué.
    Joueur adverse (pas de fiche) : le nom saisi en clair (``fallback``).
    """
    if player is None:
        return fallback
    return player.full_name if player.is_public else ANONYMOUS
