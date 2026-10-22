from django.urls import path

from . import views

app_name = "matches"

urlpatterns = [
    path("matchs/", views.match_list, name="list"),
    path("matchs/calendrier.ics", views.calendar_ics_view, name="ics"),
    path("matchs/calendrier.pdf", views.calendar_pdf_view, name="pdf"),
    path("matchs/<slug:slug>/", views.match_detail, name="detail"),
]
