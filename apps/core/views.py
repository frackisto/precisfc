from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import cache_control, never_cache
from django.views.decorators.http import require_GET, require_POST

from . import selectors
from .context_processors import THEME_COOKIE, THEMES
from .models import ClubSettings, OrgMember, President, TrophyWin, Value
from .seo import breadcrumbs_jsonld, organization_jsonld, page_seo

ONE_YEAR = 365 * 24 * 3600


def render_page(request, template, *, seo, crumbs=(), **context):
    """Rendu d'une page publique : métadonnées, fil d'Ariane et ses données structurées."""
    crumbs = list(crumbs)
    if crumbs:
        context["breadcrumbs_jsonld"] = breadcrumbs_jsonld(request, crumbs)
    return render(request, template, {"seo": seo, "crumbs": crumbs, **context})


@require_GET
@never_cache
def healthz(request):
    """Sonde de disponibilité de l'application (sans accès à la base de données)."""
    return JsonResponse({"status": "ok"})


# --- Accueil et pages du club -----------------------------------------------------


@require_GET
def home(request):
    club = ClubSettings.cached()
    return render_page(
        request,
        "core/home.html",
        seo=page_seo(request, title=club.name),
        organization_jsonld=organization_jsonld(request, club),
        **selectors.home_blocks(),
    )


CLUB_CRUMB = ("Le club", "/club/")


@require_GET
def club(request):
    club = ClubSettings.cached()
    return render_page(
        request,
        "core/club.html",
        seo=page_seo(request, title="Le club", description=club.about_short),
        crumbs=[("Le club", None)],
        pages=selectors.published_pages(),
        values=Value.objects.all(),
        title_count=TrophyWin.objects.count(),
        organization_jsonld=organization_jsonld(request, club),
    )


@require_GET
def page_detail(request, slug):
    page = get_object_or_404(selectors.published_pages(), slug=slug)
    return render_page(
        request,
        "core/page_detail.html",
        seo=page_seo(
            request,
            title=page.title,
            description=page.body,
            image=page.cover,
            obj=page,
            type="article",
        ),
        crumbs=[CLUB_CRUMB, (page.title, None)],
        page=page,
    )


@require_GET
def trophies(request):
    return render_page(
        request,
        "core/trophies.html",
        seo=page_seo(request, title="Palmarès", description="Les titres remportés par le club."),
        crumbs=[CLUB_CRUMB, ("Palmarès", None)],
        trophies=selectors.trophies_with_wins(),
    )


@require_GET
def presidents(request):
    return render_page(
        request,
        "core/presidents.html",
        seo=page_seo(request, title="Présidents", description="Les présidents successifs du club."),
        crumbs=[CLUB_CRUMB, ("Présidents", None)],
        presidents=President.objects.all(),
    )


@require_GET
def organisation(request):
    return render_page(
        request,
        "core/organisation.html",
        seo=page_seo(request, title="Organigramme", description="L'organisation du club."),
        crumbs=[CLUB_CRUMB, ("Organigramme", None)],
        members=OrgMember.objects.filter(is_published=True),
    )


@require_GET
def facilities(request):
    return render_page(
        request,
        "core/facilities.html",
        seo=page_seo(
            request,
            title="Infrastructures",
            description="Stade, centre d'entraînement et centre de formation du club.",
        ),
        crumbs=[CLUB_CRUMB, ("Infrastructures", None)],
        facilities=selectors.published_facilities(),
    )


@require_GET
def facility_detail(request, slug):
    facility = get_object_or_404(
        selectors.published_facilities().prefetch_related("photos"), slug=slug
    )
    return render_page(
        request,
        "core/facility_detail.html",
        seo=page_seo(
            request, title=facility.name, description=facility.description, image=facility.cover
        ),
        crumbs=[CLUB_CRUMB, ("Infrastructures", reverse("core:facilities")), (facility.name, None)],
        facility=facility,
    )


# --- Référencement ----------------------------------------------------------------


@require_GET
@cache_control(public=True, max_age=24 * 3600)
def robots_txt(request):
    """L'adresse de l'administration n'y figure volontairement pas (elle reste secrète)."""
    lines = [
        "User-agent: *",
        "Disallow: /compte/",
        "Disallow: /theme/",
        "",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


# --- Thème -------------------------------------------------------------------------


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
