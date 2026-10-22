from django.urls import path

from . import views

app_name = "competitions"

urlpatterns = [
    path("competitions/", views.edition_list, name="list"),
    path(
        "competitions/<slug:competition_slug>/<slug:season_slug>/",
        views.edition_detail,
        name="detail",
    ),
]
