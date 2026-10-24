from django.urls import path

from . import views

app_name = "news"

urlpatterns = [
    path("actualites/", views.article_list, name="list"),
    path("actualites/apercu/<uuid:token>/", views.article_preview, name="preview"),
    path("actualites/<slug:slug>/", views.article_detail, name="detail"),
]
