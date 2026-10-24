"""Commande demo_news : articles dans tous les statuts et comptes de démonstration."""

import pytest
from django.core.management import CommandError, call_command
from django.urls import reverse
from PIL import Image, ImageDraw

from apps.accounts.models import User
from apps.news.management.commands.demo_news import (
    COVER_HEIGHT,
    COVER_WIDTH,
    DEMO_PASSWORD,
    EDITOR_EMAIL,
    WRITER_EMAIL,
    fit_title,
)
from apps.news.models import Article, Category

pytestmark = pytest.mark.django_db


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.DEBUG = True
    return tmp_path


def test_creates_articles_in_every_status(media, client):
    call_command("demo_news", verbosity=0)

    statuses = sorted(Article.objects.values_list("status", flat=True))
    assert statuses.count("PUBLISHED") == 5
    assert {"SCHEDULED", "IN_REVIEW", "DRAFT", "ARCHIVED"} <= set(statuses)
    page = client.get(reverse("news:list")).content.decode()
    assert "Precis FC s&#x27;impose 2-0" in page
    assert "programmé" not in page and "brouillon" not in page and "archivé" not in page.lower()
    article = Article.objects.get(slug="demo-victoire-a-domicile")
    detail = client.get(article.get_absolute_url()).content.decode()
    assert "<h2>Les temps forts</h2>" in detail and ".webp" in detail


def test_demo_accounts_have_their_roles(media, client):
    call_command("demo_news", verbosity=0)

    writer, editor = User.objects.get(email=WRITER_EMAIL), User.objects.get(email=EDITOR_EMAIL)
    assert writer.has_perm("news.add_article") and not writer.has_perm("news.publish_article")
    assert editor.has_perm("news.publish_article")
    # Connexion par le formulaire du site (adresse vérifiée, mot de passe affiché).
    response = client.post(
        reverse("account_login"), {"login": WRITER_EMAIL, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 302 and "_auth_user_id" in client.session


def test_running_twice_does_not_duplicate(media):
    call_command("demo_news", verbosity=0)
    call_command("demo_news", verbosity=0)

    assert Article.objects.count() == 9 and Category.objects.count() == 2
    assert User.objects.filter(email__endswith="@demo.precisfc.test").count() == 2
    assert len(list((media / "news").rglob("*.jpg"))) == 9


def test_delete_keeps_real_content(media):
    real = Article.objects.create(title="Vrai article")
    call_command("demo_news", verbosity=0)

    call_command("demo_news", "--delete", verbosity=0)

    assert list(Article.objects.all()) == [real]
    assert not User.objects.filter(email__endswith="@demo.precisfc.test").exists()
    assert not list((media / "news").rglob("*.jpg"))


def test_refuses_to_run_outside_development(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError, match="développement"):
        call_command("demo_news", verbosity=0)


@pytest.mark.parametrize(
    "title",
    [
        "Court titre",
        "Avant-match : déplacement à Bouaké (démo)",
        "Un titre vraiment très long pour vérifier le retour à la ligne automatique dans le "
        "bandeau de l'image, même avec beaucoup de mots et une phrase qui n'en finit plus",
    ],
)
def test_cover_title_always_fits_inside_the_band(title):
    image = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT))
    draw = ImageDraw.Draw(image)

    font, _size, lines = fit_title(draw, title)

    assert 1 <= len(lines) <= 3
    assert all(draw.textlength(line, font=font) <= COVER_WIDTH - 2 * 80 for line in lines)
    assert " ".join(lines).split() == title.split()  # aucun mot perdu


def test_deleting_the_demo_also_removes_cached_versions(media, client):
    call_command("demo_news", verbosity=0)
    client.get(reverse("news:list"))  # génère les vignettes WebP
    assert list((media / "CACHE").rglob("*.webp"))

    call_command("demo_news", "--delete", verbosity=0)

    assert not list((media / "CACHE").rglob("*.webp"))
