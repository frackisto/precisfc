from django.conf import settings

from .models import ClubSettings
from .navigation import build_menu
from .seo import page_seo

THEME_COOKIE = "pfc_theme"
THEMES = ("light", "dark", "auto")


def site(request):
    """Données communes à toutes les pages : paramètres du club, menu, thème choisi."""
    theme = request.COOKIES.get(THEME_COOKIE)
    return {
        "club": ClubSettings.cached(),
        "main_menu": build_menu(request.path),
        "color_theme": theme if theme in THEMES else "auto",
        "signup_open": settings.ACCOUNT_SIGNUP_OPEN,
        # Métadonnées par défaut ; chaque vue publique fournit les siennes.
        "seo": page_seo(request),
    }
