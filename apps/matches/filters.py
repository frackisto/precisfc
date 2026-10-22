import django_filters
from django import forms
from django.utils import timezone

from apps.competitions.models import Competition, Season
from apps.teams.models import Team

from .models import Match

SELECT = forms.Select(attrs={"class": "form-select"})


class MatchFilter(django_filters.FilterSet):
    """Filtres du calendrier, transmis dans l'adresse (?saison=…&equipe=…) : partageables."""

    PERIODS = (("a-venir", "À venir"), ("resultats", "Résultats"))

    saison = django_filters.ModelChoiceFilter(
        label="Saison",
        field_name="competition_season__season",
        to_field_name="slug",
        queryset=Season.objects.all(),
        empty_label="Toutes les saisons",
        widget=SELECT,
    )
    competition = django_filters.ModelChoiceFilter(
        label="Compétition",
        field_name="competition_season__competition",
        to_field_name="slug",
        queryset=Competition.objects.all(),
        empty_label="Toutes les compétitions",
        widget=SELECT,
    )
    equipe = django_filters.ModelChoiceFilter(
        label="Équipe",
        field_name="competition_season__team",
        to_field_name="slug",
        queryset=Team.objects.filter(is_published=True),
        empty_label="Toutes les équipes",
        widget=SELECT,
    )
    periode = django_filters.ChoiceFilter(
        label="Période",
        choices=PERIODS,
        method="filter_period",
        empty_label="Tous les matchs",
        widget=SELECT,
    )

    class Meta:
        model = Match
        fields = []

    def filter_period(self, queryset, name, value):
        now = timezone.now()
        if value == "a-venir":
            return (
                queryset.filter(kickoff_at__gte=now)
                .exclude(status__in=[Match.Status.FINISHED, Match.Status.CANCELLED])
                .order_by("kickoff_at")
            )
        if value == "resultats":
            return queryset.filter(status=Match.Status.FINISHED).order_by("-kickoff_at")
        return queryset
