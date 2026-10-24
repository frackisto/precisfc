from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("finances/", views.finances, name="finances"),
    path("finances/export.csv", views.finances_export, name="finances_export"),
    path("scores/", views.scores, name="scores"),
    path("scores/<int:pk>/", views.score_update, name="score_update"),
]
