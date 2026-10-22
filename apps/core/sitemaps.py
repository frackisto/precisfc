"""Plan du site (sitemap.xml). Chaque étape y ajoute ses pages publiques."""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

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


SITEMAPS = {
    "pages": StaticPagesSitemap,
    "club-pages": PageSitemap,
    "facilities": FacilitySitemap,
}
