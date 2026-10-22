"""Lectures des contenus publics (une requête par bloc, quel que soit le volume)."""

from django.db.models import Count, Prefetch

from apps.matches.models import Match
from apps.news.models import Article
from apps.partners.models import Partner
from apps.teams.models import Player

from .models import Facility, HeroSlide, Page, Trophy, TrophyWin


def home_blocks(now=None) -> dict:
    return {
        "slides": list(HeroSlide.objects.visible(now)[:5]),
        "next_match": Match.objects.upcoming(now).own_club().first(),
        "last_result": Match.objects.results().own_club().first(),
        "articles": list(
            Article.objects.published(now)
            .select_related("category")
            .order_by("-is_featured", "-publish_at")[:6]
        ),
        "featured_players": list(
            Player.objects.public().filter(is_featured=True).select_related("team")[:4]
        ),
        "partners": list(Partner.objects.current().order_by("tier", "order", "name")[:12]),
    }


def published_pages():
    return Page.objects.filter(is_published=True)


def published_facilities():
    return Facility.objects.filter(is_published=True)


def trophies_with_wins():
    return (
        Trophy.objects.annotate(win_count=Count("wins"))
        .filter(win_count__gt=0)
        .prefetch_related(Prefetch("wins", queryset=TrophyWin.objects.order_by("-year")))
    )
