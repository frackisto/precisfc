import django_filters
from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.core.models import ClubSettings
from apps.core.seo import page_seo
from apps.core.views import render_page

from .models import Article, Category, Tag

PER_PAGE = 12
NEWS_CRUMB = ("Actualités", "/actualites/")
SELECT = forms.Select(attrs={"class": "form-select"})


class ArticleFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        label="Rechercher",
        method="search",
        widget=forms.TextInput(attrs={"class": "form-control", "type": "search"}),
    )
    categorie = django_filters.ModelChoiceFilter(
        label="Catégorie",
        field_name="category",
        to_field_name="slug",
        queryset=Category.objects.all(),
        empty_label="Toutes les catégories",
        widget=SELECT,
    )
    type = django_filters.ChoiceFilter(
        label="Type",
        field_name="kind",
        choices=Article.Kind.choices,
        empty_label="Tous les types",
        widget=SELECT,
    )
    motcle = django_filters.ModelChoiceFilter(
        label="Mot-clé",
        field_name="tags",
        to_field_name="slug",
        queryset=Tag.objects.all(),
        empty_label="Tous les mots-clés",
        widget=SELECT,
    )

    class Meta:
        model = Article
        fields = []

    def search(self, queryset, name, value):
        # Recherche insensible à la casse et aux accents (collation utf8mb4_unicode_ci).
        terms = value.split()[:8]
        for term in terms:
            queryset = queryset.filter(
                Q(title__icontains=term) | Q(excerpt__icontains=term) | Q(body__icontains=term)
            )
        return queryset


@require_GET
def article_list(request):
    base = Article.objects.published().select_related("category").order_by("-publish_at")
    article_filter = ArticleFilter(request.GET, queryset=base)
    page = Paginator(article_filter.qs.distinct(), PER_PAGE).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render_page(
        request,
        "news/article_list.html",
        seo=page_seo(request, title="Actualités", description="Toute l'actualité du club."),
        crumbs=[("Actualités", None)],
        filter=article_filter,
        page=page,
        query_string=query.urlencode(),
    )


def _article_context(request, article):
    club = ClubSettings.cached()
    related = (
        Article.objects.published()
        .exclude(pk=article.pk)
        .filter(Q(category=article.category_id) | Q(tags__in=article.tags.all()))
        .distinct()
        .select_related("category")
        .order_by("-publish_at")[:3]
        if article.category_id or article.tags.exists()
        else Article.objects.none()
    )
    absolute_url = request.build_absolute_uri(article.get_absolute_url())
    news_jsonld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": article.title[:110],
        "datePublished": article.publish_at.isoformat() if article.publish_at else None,
        "dateModified": article.updated_at.isoformat(),
        "mainEntityOfPage": absolute_url,
        "publisher": {"@type": "SportsTeam", "name": club.name},
    }
    if article.author:
        news_jsonld["author"] = {"@type": "Person", "name": str(article.author)}
    if article.cover_image:
        news_jsonld["image"] = request.build_absolute_uri(article.cover_image.url)
    return {
        "article": article,
        "related": related,
        "players": [player for player in article.related_players.all() if player.is_public],
        "share_url": absolute_url,
        "page_jsonld": {key: value for key, value in news_jsonld.items() if value is not None},
    }


@require_GET
def article_detail(request, slug):
    article = get_object_or_404(
        Article.objects.published().select_related(
            "category", "author", "gallery", "related_match__home_club", "related_match__away_club"
        ),
        slug=slug,
    )
    return render_page(
        request,
        "news/article_detail.html",
        seo=page_seo(
            request,
            title=article.title,
            description=article.excerpt or article.body,
            image=article.cover_image,
            obj=article,
            type="article",
        ),
        crumbs=[NEWS_CRUMB, (article.title, None)],
        **_article_context(request, article),
    )


@require_GET
@never_cache
@login_required
@permission_required("news.view_article", raise_exception=True)
def article_preview(request, token):
    """Aperçu d'un article quel que soit son statut, réservé à l'équipe éditoriale."""
    article = get_object_or_404(
        Article.objects.select_related("category", "author", "gallery"), preview_token=token
    )
    return render_page(
        request,
        "news/article_detail.html",
        seo=page_seo(request, title=f"Aperçu : {article.title}", noindex=True),
        crumbs=[NEWS_CRUMB, ("Aperçu", None)],
        is_preview=True,
        **_article_context(request, article),
    )
