from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.core.sitemaps import SITEMAPS

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("compte/", include("allauth.urls")),
    path("compte/", include("apps.accounts.urls")),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("", include("apps.core.urls")),
    path("", include("apps.teams.urls")),
    path("", include("apps.matches.urls")),
    path("", include("apps.competitions.urls")),
    path("", include("apps.news.urls")),
    path("", include("apps.media_library.urls")),
]

if settings.DEBUG:
    # En production, les médias publics sont servis par Apache (public_html/media).
    # Les fichiers privés ne sont jamais servis par une URL statique.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if "debug_toolbar" in settings.INSTALLED_APPS:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()
