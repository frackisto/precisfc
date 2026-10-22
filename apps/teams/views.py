from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from apps.competitions.models import PlayerSeasonStat
from apps.core.seo import page_seo
from apps.core.views import render_page
from apps.matches.models import Match

from .models import Player, Team

TEAMS_CRUMB = ("Équipes", "/equipes/")


@require_GET
def team_list(request):
    return render_page(
        request,
        "teams/team_list.html",
        seo=page_seo(
            request,
            title="Équipes",
            description="Les équipes du club, de l'équipe première à l'académie.",
        ),
        crumbs=[("Équipes", None)],
        teams=Team.objects.filter(is_published=True).select_related("head_coach"),
    )


@require_GET
def team_detail(request, slug):
    team = get_object_or_404(Team.objects.filter(is_published=True), slug=slug)
    # Joueurs publics seulement : jamais un mineur sans consentement.
    players = list(team.players.public().order_by("shirt_number", "last_name"))
    squad = [
        (label, [player for player in players if player.position == position])
        for position, label in Player.Position.choices
    ]
    team_matches = Match.objects.filter(competition_season__team=team)
    return render_page(
        request,
        "teams/team_detail.html",
        seo=page_seo(request, title=team.name, description=team.description, image=team.image),
        crumbs=[TEAMS_CRUMB, (team.name, None)],
        team=team,
        squad=[(label, group) for label, group in squad if group],
        staff=team.staff.filter(is_published=True),
        upcoming=list(team_matches.upcoming().own_club()[:5]),
        results=list(team_matches.results().own_club()[:5]),
    )


@require_GET
def player_detail(request, slug):
    player = get_object_or_404(Player.objects.public().select_related("team"), slug=slug)
    stats = (
        PlayerSeasonStat.objects.filter(player=player)
        .select_related("season", "competition_season__competition")
        .order_by("-season__start_date", "competition_season__competition__name")
    )
    person = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": player.full_name,
        "jobTitle": f"Footballeur ({player.get_position_display()})",
        "memberOf": {"@type": "SportsTeam", "name": player.team.name},
    }
    if player.photo:
        person["image"] = request.build_absolute_uri(player.photo.url)
    return render_page(
        request,
        "teams/player_detail.html",
        seo=page_seo(
            request,
            title=player.full_name,
            description=player.bio or f"{player.get_position_display()}, {player.team.name}",
            image=player.photo,
            type="profile",
        ),
        crumbs=[
            TEAMS_CRUMB,
            (player.team.name, player.team.get_absolute_url()),
            (player.full_name, None),
        ],
        player=player,
        stats=stats,
        photos=player.photos.all(),
        page_jsonld=person,
    )
