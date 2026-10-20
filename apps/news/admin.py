from django.contrib import admin

from apps.accounts.permissions import can_change_article, can_publish_article
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

    # Champs que seules les personnes habilitées à publier peuvent modifier.
    PUBLISHER_FIELDS = ("status", "publish_at", "is_featured", "author", "review_note")

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return super().has_change_permission(request)
        return can_change_article(request.user, obj)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if can_publish_article(request.user):
            return fields
        return (*fields, *self.PUBLISHER_FIELDS)

    def save_model(self, request, obj, form, change):
        if not change and obj.author_id is None:
            obj.author = request.user
        super().save_model(request, obj, form, change)
