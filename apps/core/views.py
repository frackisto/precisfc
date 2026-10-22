from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import cache_control, never_cache
from django.views.decorators.http import require_GET, require_POST

from .context_processors import THEME_COOKIE, THEMES
from .models import ClubSettings

ONE_YEAR = 365 * 24 * 3600


@require_GET
@never_cache
def healthz(request):
    """Sonde de disponibilité de l'application (sans accès à la base de données)."""
    return JsonResponse({"status": "ok"})


@require_GET
def home(request):
    """Page d'accueil provisoire ; la page complète est construite à l'étape 7."""
    return render(request, "core/home.html")


@require_GET
@cache_control(public=True, max_age=ONE_YEAR)
def theme_css(request):
    """Couleurs du club en variables CSS (servi sous une URL versionnée : ?v=…).

    Une feuille de style plutôt qu'un bloc <style> dans la page : compatible avec la
    politique de sécurité des contenus (CSP) stricte de l'étape 15.
    """
    club = ClubSettings.cached()
    return render(
        request, "core/theme.css", {"palette": club.palette}, content_type="text/css; charset=utf-8"
    )


@require_POST
def set_theme(request):
    """Choix clair / sombre / automatique, mémorisé dans un cookie.

    Fonctionne sans JavaScript (simple formulaire) ; avec JavaScript, app.js change le
    thème sans recharger la page et appelle cette vue en arrière-plan.
    """
    theme = request.POST.get("theme")
    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = reverse("core:home")
    response = HttpResponseRedirect(next_url)
    if theme in THEMES:
        response.set_cookie(
            THEME_COOKIE,
            theme,
            max_age=ONE_YEAR,
            samesite="Lax",
            secure=settings.SESSION_COOKIE_SECURE,
            httponly=False,  # lu par theme-init.js pour appliquer le thème avant l'affichage
        )
    return response
