from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz/", views.healthz, name="healthz"),
    path("theme.css", views.theme_css, name="theme_css"),
    path("theme/", views.set_theme, name="set_theme"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("club/", views.club, name="club"),
    path("club/palmares/", views.trophies, name="trophies"),
    path("club/presidents/", views.presidents, name="presidents"),
    path("club/organigramme/", views.organisation, name="organisation"),
    path("club/infrastructures/", views.facilities, name="facilities"),
    path("club/infrastructures/<slug:slug>/", views.facility_detail, name="facility_detail"),
    # En dernier : les pages institutionnelles (histoire, valeurs…) par leur slug.
    path("club/<slug:slug>/", views.page_detail, name="page_detail"),
]
