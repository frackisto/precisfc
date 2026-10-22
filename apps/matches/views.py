from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.core.models import ClubSettings
from apps.core.seo import page_seo
from apps.core.views import render_page

from .exports import calendar_ics, calendar_pdf, match_title
from .filters import MatchFilter
from .models import LineupEntry, Match, MatchEvent

PER_PAGE = 20
MATCHES_CRUMB = ("Matchs", "/matchs/")


def filtered_matches(request):
    """Matchs publiés de notre club, filtrés selon l'adresse (?saison=…&equipe=…)."""
    base = Match.objects.public().own_club().order_by("kickoff_at")
    return MatchFilter(request.GET, queryset=base)


@require_GET
def match_list(request):
    match_filter = filtered_matches(request)
    page = Paginator(match_filter.qs, PER_PAGE).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render_page(
        request,
        "matches/match_list.html",
        seo=page_seo(
            request,
            title="Calendrier et résultats",
            description="Tous les matchs du club : calendrier, résultats et classements.",
        ),
        crumbs=[("Matchs", None)],
        filter=match_filter,
        page=page,
        query_string=query.urlencode(),
    )


@require_GET
def match_detail(request, slug):
    lineup = LineupEntry.objects.select_related("player").order_by("-is_starter", "order", "pk")
    events = MatchEvent.objects.select_related("player", "assist_player", "player_out")
    match = get_object_or_404(
        Match.objects.public().prefetch_related(
            Prefetch("lineup", queryset=lineup),
            Prefetch("events", queryset=events.order_by("minute", "added_time", "pk")),
            "team_stats",
        ),
        slug=slug,
    )
    lineups = {
        side: [entry for entry in match.lineup.all() if entry.side == side]
        for side in ("HOME", "AWAY")
    }
    stats = {stat.side: stat for stat in match.team_stats.all()}
    venue = match.venue.name if match.venue else match.venue_name
    event_jsonld = {
        "@context": "https://schema.org",
        "@type": "SportsEvent",
        "name": match_title(match),
        "startDate": timezone.localtime(match.kickoff_at).isoformat(),
        "sport": "Football",
        "homeTeam": {"@type": "SportsTeam", "name": match.home_club.name},
        "awayTeam": {"@type": "SportsTeam", "name": match.away_club.name},
        "eventStatus": {
            "CANCELLED": "https://schema.org/EventCancelled",
            "POSTPONED": "https://schema.org/EventPostponed",
        }.get(match.status, "https://schema.org/EventScheduled"),
    }
    if venue:
        event_jsonld["location"] = {"@type": "Place", "name": venue}
    return render_page(
        request,
        "matches/match_detail.html",
        seo=page_seo(
            request,
            title=match_title(match),
            description=(
                f"{match.competition_season.competition.name} — "
                f"{timezone.localtime(match.kickoff_at):%d/%m/%Y %H:%M}"
            ),
            type="article",
        ),
        crumbs=[MATCHES_CRUMB, (match_title(match), None)],
        match=match,
        home_lineup=lineups["HOME"],
        away_lineup=lineups["AWAY"],
        home_stats=stats.get("HOME"),
        away_stats=stats.get("AWAY"),
        page_jsonld=event_jsonld,
    )


def _export_matches(request):
    return filtered_matches(request).qs.order_by("kickoff_at")


@require_GET
def calendar_ics_view(request):
    club = ClubSettings.cached()
    content = calendar_ics(
        _export_matches(request),
        calendar_name=f"{club.name} — matchs",
        domain=request.get_host().split(":")[0],
        url_for=lambda match: request.build_absolute_uri(match.get_absolute_url()),
    )
    response = HttpResponse(content, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="calendrier-precis-fc.ics"'
    return response


@require_GET
def calendar_pdf_view(request):
    club = ClubSettings.cached()
    content = calendar_pdf(
        _export_matches(request),
        title="Calendrier des matchs",
        club_name=club.name,
        primary=club.color_primary,
    )
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="calendrier-precis-fc.pdf"'
    return response
