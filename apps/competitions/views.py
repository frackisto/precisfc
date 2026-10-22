from itertools import groupby

from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from apps.core.seo import page_seo
from apps.core.views import render_page
from apps.teams.models import Player

from .models import CompetitionSeason, PlayerSeasonStat, Season, Standing

LEADERS = 10


def public_player_stats(edition):
    """Statistiques des joueurs visibles publiquement (jamais un mineur sans consentement)."""
    return PlayerSeasonStat.objects.filter(
        competition_season=edition, player__in=Player.objects.public()
    ).select_related("player__team")


@require_GET
def edition_list(request):
    current = Season.current()
    editions = CompetitionSeason.objects.select_related("competition", "season", "team")
    if current:
        editions = editions.filter(season=current)
    return render_page(
        request,
        "competitions/edition_list.html",
        seo=page_seo(
            request, title="Classements", description="Classements et statistiques du club."
        ),
        crumbs=[("Matchs", "/matchs/"), ("Classements", None)],
        editions=editions.order_by("team__order", "competition__name"),
        season=current,
    )


@require_GET
def edition_detail(request, competition_slug, season_slug):
    edition = get_object_or_404(
        CompetitionSeason.objects.select_related("competition", "season", "team"),
        competition__slug=competition_slug,
        season__slug=season_slug,
    )
    standings = list(
        Standing.objects.filter(competition_season=edition)
        .select_related("club")
        .order_by("group_name", "position")
    )
    groups = [
        (group, list(rows)) for group, rows in groupby(standings, key=lambda row: row.group_name)
    ]
    stats = public_player_stats(edition)
    scorers = list(
        stats.filter(goals__gt=0).order_by("-goals", "-assists", "player__last_name")[:LEADERS]
    )
    passers = list(
        stats.filter(assists__gt=0).order_by("-assists", "-goals", "player__last_name")[:LEADERS]
    )
    title = f"{edition.competition.name} {edition.season.name}"
    return render_page(
        request,
        "competitions/edition_detail.html",
        seo=page_seo(
            request,
            title=f"Classement {title}",
            description=f"Classement, buteurs et passeurs — {title}.",
        ),
        crumbs=[("Matchs", "/matchs/"), ("Classements", "/competitions/"), (title, None)],
        edition=edition,
        groups=groups,
        best_attack=max(standings, key=lambda row: row.goals_for, default=None),
        best_defence=min(
            (row for row in standings if row.played),
            key=lambda row: row.goals_against,
            default=None,
        ),
        scorers=scorers,
        passers=passers,
        scorers_chart={
            "labels": [stat.player.full_name for stat in scorers],
            "values": [stat.goals for stat in scorers],
        },
    )
