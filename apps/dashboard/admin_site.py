"""Administration Django personnalisée : nom et couleurs du club, rubriques dans un ordre
métier (le club, le sport, les contenus, la boutique…) plutôt qu'alphabétique, et lien
vers le tableau de bord."""

from django.contrib import admin
from django.urls import reverse

from apps.accounts.roles import DASHBOARD
from apps.core.models import ClubSettings

APP_ORDER = [
    "core",
    "teams",
    "competitions",
    "matches",
    "news",
    "media_library",
    "partners",
    "shop",
    "orders",
    "payments",
    "ticketing",
    "academy",
    "contact",
    "notifications",
    "accounts",
    "auth",
    "account",
    "auditlog",
    "axes",
]


class ClubAdminSite(admin.AdminSite):
    index_title = "Administration du site"

    def each_context(self, request):
        context = super().each_context(request)
        club = ClubSettings.cached()
        context["site_header"] = f"{club.name} — administration"
        context["site_title"] = f"Administration {club.name}"
        user = request.user
        context["dashboard_url"] = (
            reverse("dashboard:home") if user.is_active and user.has_perm(DASHBOARD) else ""
        )
        return context

    def get_app_list(self, request, app_label=None):
        apps = super().get_app_list(request, app_label)
        rank = {label: index for index, label in enumerate(APP_ORDER)}
        return sorted(apps, key=lambda app: (rank.get(app["app_label"], len(rank)), app["name"]))
