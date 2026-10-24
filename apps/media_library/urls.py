from django.urls import path

from . import views

app_name = "media_library"

urlpatterns = [
    path("medias/", views.media_index, name="index"),
    path("medias/albums/<slug:slug>/", views.album_detail, name="album"),
    path("medias/videos/<slug:slug>/", views.video_detail, name="video"),
]
