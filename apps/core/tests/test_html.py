"""Assainissement du texte enrichi : tentatives d'injection de script (XSS)."""

import pytest

from apps.core.html import render_rich_text, sanitize_html
from apps.core.models import Page
from apps.news.models import Article

ATTACKS = [
    "<script>alert(1)</script>",
    '<img src="x" onerror="alert(1)">',
    '<a href="javascript:alert(1)">clic</a>',
    '<a href="JaVaScRiPt:alert(1)">clic</a>',
    '<p onmouseover="alert(1)">survol</p>',
    '<svg onload="alert(1)"></svg>',
    '<iframe src="https://site-pirate.example"></iframe>',
    '<p style="background:url(javascript:alert(1))">style</p>',
    "<style>body{display:none}</style>",
    '<form action="https://site-pirate.example"><input name="mdp"></form>',
    '<a href="data:text/html;base64,PHNjcmlwdD4=">données</a>',
    "<!-- <script>alert(1)</script> -->",
]


@pytest.mark.parametrize("attack", ATTACKS)
def test_attacks_are_neutralised(attack):
    cleaned = sanitize_html(attack).lower()

    for dangerous in (
        "<script",
        "onerror",
        "onload",
        "onmouseover",
        "javascript:",
        "<iframe",
        "<style",
        "<form",
        "data:",
    ):
        assert dangerous not in cleaned


def test_allowed_formatting_is_kept():
    html = (
        "<h2>Titre</h2>"
        "<p><strong>Gras</strong>, <em>italique</em>, <u>souligné</u>, <s>barré</s></p>"
        '<ul><li>Un</li></ul><ol start="3"><li>Trois</li></ol>'
        "<blockquote>Citation</blockquote><hr>"
    )

    assert sanitize_html(html) == html


def test_links_are_kept_with_safe_rel():
    cleaned = sanitize_html('<a href="https://precisfc.com" target="_blank">Site</a>')

    assert cleaned == '<a href="https://precisfc.com" rel="noopener noreferrer">Site</a>'


def test_heading_level_one_is_not_allowed_in_content():
    assert sanitize_html("<h1>Titre</h1>") == "Titre"


@pytest.mark.django_db
@pytest.mark.parametrize("model", [Article, Page])
def test_content_is_sanitized_when_saved(model):
    extra = {"section": "HISTORY"} if model is Page else {}
    obj = model.objects.create(title="Test", body="<p>Texte</p><script>alert(1)</script>", **extra)

    obj.refresh_from_db()
    assert obj.body == "<p>Texte</p>"


@pytest.mark.django_db
def test_content_inserted_directly_in_database_is_sanitized_on_display():
    article = Article.objects.create(title="Test")
    Article.objects.filter(pk=article.pk).update(body='<p>Ok</p><img src=x onerror="alert(1)">')
    article.refresh_from_db()

    assert render_rich_text(article.body) == "<p>Ok</p>"
