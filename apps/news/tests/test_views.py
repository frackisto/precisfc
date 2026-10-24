"""Pages publiques des actualités : liste, recherche, filtres, article, plan du site."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.utils import years_ago
from apps.news.models import Article, Category, Tag
from tests.factories import PlayerFactory

pytestmark = pytest.mark.django_db


def html(response):
    return response.content.decode()


def published(title, **kwargs):
    values = {
        "title": title,
        "body": "<p>Contenu</p>",
        "status": "PUBLISHED",
        "publish_at": timezone.now() - timedelta(hours=1),
    }
    return Article.objects.create(**{**values, **kwargs})


def test_list_shows_only_visible_articles(client):
    published("Article publié")
    Article.objects.create(title="Brouillon secret")
    published("Programmé demain", status="SCHEDULED", publish_at=timezone.now() + timedelta(days=1))
    published("Archivé", status="ARCHIVED")

    page = html(client.get(reverse("news:list")))

    assert "Article publié" in page
    assert "Brouillon secret" not in page and "Programmé demain" not in page
    assert "Archivé" not in page


def test_search_ignores_case_and_accents(client):
    published("Victoire de l'Équipe première", body="<p>Un match rythmé</p>")
    published("Autre sujet")

    by_title = html(client.get(reverse("news:list"), {"q": "equipe"}))
    by_body = html(client.get(reverse("news:list"), {"q": "RYTHME"}))

    assert "Victoire de l&#x27;Équipe" in by_title and "Autre sujet" not in by_title
    assert "Victoire" in by_body


def test_filters_by_category_type_and_tag(client):
    transfers = Category.objects.create(name="Mercato")
    tag = Tag.objects.create(name="Académie")
    first = published("Arrivée d'un attaquant", category=transfers, kind="TRANSFER")
    published("Interview du coach", kind="INTERVIEW")
    first.tags.add(tag)

    assert "Arrivée" in html(client.get(reverse("news:list"), {"categorie": transfers.slug}))
    assert "Interview du coach" not in html(client.get(reverse("news:list"), {"type": "TRANSFER"}))
    assert "Arrivée" in html(client.get(reverse("news:list"), {"motcle": tag.slug}))


def test_list_is_paginated(client):
    for number in range(14):
        published(f"Article {number:02d}", publish_at=timezone.now() - timedelta(hours=number + 1))

    page = html(client.get(reverse("news:list")))

    assert "Page 1 sur 2" in page and "Article 00" in page and "Article 13" not in page


def test_article_page(client):
    category = Category.objects.create(name="Communiqués")
    article = published(
        "Nouvel entraîneur",
        excerpt="Le club annonce l'arrivée de son nouvel entraîneur.",
        body="<h2>Un projet ambitieux</h2><p>Texte <strong>important</strong>.</p>",
        category=category,
    )
    published("Autre communiqué", category=category)

    page = html(client.get(article.get_absolute_url()))

    assert "<h2>Un projet ambitieux</h2>" in page and "<strong>important</strong>" in page
    assert '"@type": "NewsArticle"' in page
    assert "facebook.com/sharer" in page and "wa.me" in page
    assert "À lire aussi" in page and "Autre communiqué" in page


def test_unpublished_articles_have_no_public_page(client):
    article = Article.objects.create(title="Brouillon")
    future = published("Demain", status="SCHEDULED", publish_at=timezone.now() + timedelta(days=1))

    assert client.get(article.get_absolute_url()).status_code == 404
    assert client.get(future.get_absolute_url()).status_code == 404


def test_article_does_not_name_a_minor_without_consent(client):
    article = published("Le centre de formation brille")
    article.related_players.add(
        PlayerFactory(first_name="Adulte", last_name="Cité"),
        PlayerFactory(first_name="Enfant", last_name="Protégé", birth_date=years_ago(14)),
    )

    page = html(client.get(article.get_absolute_url()))

    assert "Adulte Cité" in page and "Protégé" not in page


def test_home_article_cards_link_to_articles(client):
    article = published("Grande victoire")

    page = html(client.get("/"))

    assert article.get_absolute_url() in page and 'href="/actualites/"' in page


def test_sitemap_lists_published_articles_only(client):
    visible = published("Visible")
    hidden = Article.objects.create(title="Caché")

    sitemap = html(client.get("/sitemap.xml"))

    assert visible.get_absolute_url() in sitemap and hidden.get_absolute_url() not in sitemap
