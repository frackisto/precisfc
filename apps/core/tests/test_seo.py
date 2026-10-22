"""Référencement : métadonnées, Open Graph, données structurées, sitemap, robots.txt."""

import json
import re
from xml.etree import ElementTree  # noqa: S405  (XML produit par notre propre site)

import pytest
from django.conf import settings
from django.urls import reverse

from apps.core.models import ClubSettings, Facility, Page
from apps.core.seo import summarize
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def html(response):
    return response.content.decode()


def meta(page, attribute, name):
    match = re.search(rf'<meta {attribute}="{name}" content="([^"]*)"', page)
    return match.group(1) if match else None


def jsonld_blocks(page):
    return [
        json.loads(block)
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
    ]


# --- Métadonnées ---------------------------------------------------------------------


def test_canonical_url_is_absolute_and_ignores_query_string(client):
    page = html(client.get("/club/?utm_source=facebook"))

    assert '<link rel="canonical" href="http://testserver/club/">' in page
    assert meta(page, "property", "og:url") == "http://testserver/club/"


def test_page_metadata_comes_from_its_seo_fields(client):
    Page.objects.create(
        section="HISTORY",
        title="Notre histoire",
        body="Texte long de la page.",
        meta_title="Histoire de Precis FC depuis 1985",
        meta_description="Les grandes dates du club.",
        og_image="seo/histoire.jpg",
        is_published=True,
    )

    page = html(client.get("/club/notre-histoire/"))

    assert "<title>Histoire de Precis FC depuis 1985 — Precis FC</title>" in page
    assert meta(page, "name", "description") == "Les grandes dates du club."
    assert meta(page, "property", "og:image") == "http://testserver/media/seo/histoire.jpg"
    assert meta(page, "property", "og:type") == "article"


def test_description_falls_back_to_page_text_without_html():
    assert summarize("<p>Fondé <strong>en 1985</strong>.</p>") == "Fondé en 1985."
    assert len(summarize("mot " * 100)) <= 160


def test_description_falls_back_to_club_defaults(client):
    club = ClubSettings.load()
    club.default_meta_description = "Site officiel du Precis FC, club de football ivoirien."
    club.save()

    page = html(client.get(reverse("core:presidents")))

    assert meta(page, "property", "og:title") == "Présidents"
    assert meta(page, "name", "description") == "Les présidents successifs du club."
    assert meta(html(client.get("/")), "name", "description") == club.default_meta_description


def test_public_pages_are_indexable_but_private_ones_are_not(client):
    assert 'name="robots"' not in html(client.get("/"))
    assert 'content="noindex, nofollow"' in html(client.get(reverse("account_login")))
    assert 'content="noindex, nofollow"' in html(client.get("/page-inexistante/"))
    client.force_login(UserFactory())
    assert 'content="noindex, nofollow"' in html(client.get(reverse("accounts:profile")))


# --- Données structurées --------------------------------------------------------------------


def test_home_describes_the_club_as_a_sports_team(client):
    club = ClubSettings.load()
    club.founded_year = 1985
    club.facebook_url = "https://facebook.com/precisfc"
    club.save()

    blocks = jsonld_blocks(html(client.get("/")))
    team = next(block for block in blocks if block["@type"] == "SportsTeam")

    assert team["name"] == "Precis FC"
    assert team["foundingDate"] == "1985"
    assert team["sameAs"] == ["https://facebook.com/precisfc"]


def test_structured_data_cannot_break_out_of_its_script_tag(client):
    club = ClubSettings.load()
    club.name = "</script><script>alert(1)</script>"
    club.save()

    page = html(client.get("/"))

    assert "</script><script>alert(1)" not in page
    assert jsonld_blocks(page)[0]["name"] == "</script><script>alert(1)</script>"


def test_breadcrumbs_are_shown_and_described(client):
    Facility.objects.create(name="Stade municipal", kind="STADIUM")

    page = html(client.get("/club/infrastructures/stade-municipal/"))
    trail = next(block for block in jsonld_blocks(page) if block["@type"] == "BreadcrumbList")

    assert 'aria-label="Fil d\'Ariane"' in page
    assert [item["name"] for item in trail["itemListElement"]] == [
        "Accueil",
        "Le club",
        "Infrastructures",
        "Stade municipal",
    ]
    assert trail["itemListElement"][2]["item"] == "http://testserver/club/infrastructures/"


# --- Sitemap et robots.txt ---------------------------------------------------------------


def test_sitemap_is_valid_xml_listing_public_pages_only(client):
    Page.objects.create(section="HISTORY", title="Notre histoire", is_published=True)
    Page.objects.create(section="OTHER", title="Brouillon")
    Facility.objects.create(name="Stade municipal", kind="STADIUM")
    Facility.objects.create(name="Projet secret", kind="OFFICE", is_published=False)

    response = client.get("/sitemap.xml")
    root = ElementTree.fromstring(  # noqa: S314
        response.content
    )
    urls = [node.text for node in root.findall("sm:url/sm:loc", SITEMAP_NS)]

    assert response.status_code == 200
    assert "http://testserver/" in urls
    assert "http://testserver/club/" in urls
    assert "http://testserver/club/notre-histoire/" in urls
    assert "http://testserver/club/infrastructures/stade-municipal/" in urls
    assert not any("brouillon" in url or "projet-secret" in url for url in urls)
    assert root.find("sm:url/sm:lastmod", SITEMAP_NS) is not None


def test_every_sitemap_url_answers(client):
    Page.objects.create(section="HISTORY", title="Notre histoire", is_published=True)
    Facility.objects.create(name="Stade municipal", kind="STADIUM")

    root = ElementTree.fromstring(  # noqa: S314
        client.get("/sitemap.xml").content
    )
    for node in root.findall("sm:url/sm:loc", SITEMAP_NS):
        assert client.get(node.text.replace("http://testserver", "")).status_code == 200, node.text


def test_robots_txt_points_to_sitemap_without_revealing_the_admin(client):
    response = client.get("/robots.txt")
    content = html(response)

    assert response["Content-Type"].startswith("text/plain")
    assert "Sitemap: http://testserver/sitemap.xml" in content
    assert "Disallow: /compte/" in content
    assert settings.ADMIN_URL not in content
