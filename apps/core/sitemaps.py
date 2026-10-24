"""Plan du site (sitemap.xml). Chaque étape y ajoute ses pages publiques."""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.competitions.models import CompetitionSeason
from apps.matches.models import Match
from apps.media_library.models import Album, Video
from apps.media_library.views import published as published_media
from apps.news.models import Article
from apps.teams.models import Player, Team

from . import selectors


class StaticPagesSitemap(Sitemap):
    changefreq = "weekly"

    def items(self):
        return [
            ("core:home", 1.0),
            ("core:club", 0.8),
            ("core:trophies", 0.6),
            ("core:presidents", 0.5),
            ("core:organisation", 0.5),
            ("core:facilities", 0.6),
            ("teams:list", 0.8),
            ("matches:list", 0.9),
            ("competitions:list", 0.8),
            ("news:list", 0.9),
            ("media_library:index", 0.7),
        ]

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]


class PageSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return selectors.published_pages().order_by("pk")

    def lastmod(self, page):
        return page.updated_at


class FacilitySitemap(Sitemap):
    changefreq = "yearly"
    priority = 0.5

    def items(self):
        return selectors.published_facilities().order_by("pk")

    def lastmod(self, facility):
        return facility.updated_at


class TeamSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Team.objects.filter(is_published=True).order_by("pk")

    def lastmod(self, team):
        return team.updated_at


class PlayerSitemap(Sitemap):
    """Joueurs publics uniquement : jamais un mineur sans consentement."""

    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Player.objects.public().order_by("pk")

    def lastmod(self, player):
        return player.updated_at


class MatchSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.6

    def items(self):
        return Match.objects.public().own_club().order_by("pk")

    def lastmod(self, match):
        return match.updated_at


class EditionSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.6

    def items(self):
        return CompetitionSeason.objects.select_related("competition", "season").order_by("pk")


class ArticleSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Article.objects.published().order_by("pk")

    def lastmod(self, article):
        return article.updated_at


class AlbumSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return published_media(Album.objects).order_by("pk")

    def lastmod(self, album):
        return album.updated_at


class VideoSitemap(AlbumSitemap):
    def items(self):
        return published_media(Video.objects).order_by("pk")


SITEMAPS = {
    "pages": StaticPagesSitemap,
    "club-pages": PageSitemap,
    "facilities": FacilitySitemap,
    "teams": TeamSitemap,
    "players": PlayerSitemap,
    "matches": MatchSitemap,
    "competitions": EditionSitemap,
    "news": ArticleSitemap,
    "albums": AlbumSitemap,
    "videos": VideoSitemap,
}
