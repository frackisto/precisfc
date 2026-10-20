"""Actualités : types, statuts et jeton de prévisualisation."""

import pytest
from django.utils import timezone

from apps.news.models import Article
from tests.helpers import rejected_by_database

pytestmark = pytest.mark.django_db


def test_article_kinds_cover_the_nine_content_types():
    assert len(Article.Kind.choices) == 9


def test_new_article_is_a_draft_with_a_unique_preview_token():
    first = Article.objects.create(title="Victoire à domicile")
    second = Article.objects.create(title="Victoire à domicile")

    assert first.status == Article.Status.DRAFT
    assert first.preview_token != second.preview_token
    assert second.slug == "victoire-a-domicile-2"


@pytest.mark.parametrize("status", [Article.Status.SCHEDULED, Article.Status.PUBLISHED])
def test_scheduled_or_published_article_requires_a_date(status):
    with rejected_by_database():
        Article.objects.create(title="Communiqué", status=status)


def test_published_article_with_date_is_accepted():
    article = Article.objects.create(
        title="Communiqué", status=Article.Status.PUBLISHED, publish_at=timezone.now()
    )

    assert article.pk is not None
