from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz/", views.healthz, name="healthz"),
    path("theme.css", views.theme_css, name="theme_css"),
    path("theme/", views.set_theme, name="set_theme"),
]
