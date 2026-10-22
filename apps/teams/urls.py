from django.urls import path

from . import views

app_name = "teams"

urlpatterns = [
    path("equipes/", views.team_list, name="list"),
    path("equipes/<slug:slug>/", views.team_detail, name="detail"),
    path("joueurs/<slug:slug>/", views.player_detail, name="player"),
]
