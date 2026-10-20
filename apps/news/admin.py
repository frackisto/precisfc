from django.contrib import admin

from apps.core.admin import SEO_FIELDSET

from .models import Article, Category, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    list_editable = ("order",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """Administration de base ; le workflow de relecture par rôle arrive à l'étape 9."""

    list_display = ("title", "kind", "category", "status", "publish_at", "author", "is_featured")
    list_filter = ("status", "kind", "category", "is_featured")
    search_fields = ("title", "excerpt", "body")
    date_hierarchy = "publish_at"
    prepopulated_fields = {"slug": ("title",)}
    list_select_related = ("category", "author")
    autocomplete_fields = ("tags", "related_match", "related_players", "gallery", "author")
    readonly_fields = ("reviewed_by", "reviewed_at", "preview_token")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "kind",
                    "title",
                    "slug",
                    "excerpt",
                    "body",
                    ("cover_image", "cover_alt"),
                    "gallery",
                )
            },
        ),
        ("Classement", {"fields": ("category", "tags", "related_match", "related_players")}),
        (
            "Publication",
            {
                "fields": (
                    "status",
                    "publish_at",
                    "author",
                    "is_featured",
                    ("reviewed_by", "reviewed_at"),
                    "review_note",
                    "preview_token",
                )
            },
        ),
        SEO_FIELDSET,
    )
