from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from apps.accounts.permissions import can_change_article, can_publish_article
from apps.core.admin import SEO_FIELDSET

from .models import Article, Category, Tag
from .services import workflow


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
    """Articles : le statut ne change que par les boutons du circuit de publication
    (services/workflow.py), qui vérifient le rôle et tracent la relecture."""

    change_form_template = "admin/news/article/change_form.html"
    list_display = ("title", "kind", "category", "status", "publish_at", "author", "is_featured")
    list_filter = ("status", "kind", "category", "is_featured")
    search_fields = ("title", "excerpt", "body")
    date_hierarchy = "publish_at"
    prepopulated_fields = {"slug": ("title",)}
    list_select_related = ("category", "author")
    autocomplete_fields = ("tags", "related_match", "related_players", "gallery", "author")
    readonly_fields = ("status", "reviewed_by", "reviewed_at", "preview_link")
    actions = ["publish_selected", "archive_selected"]
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
                "description": (
                    "Pour programmer, indiquez une date future puis « Publier ou programmer »."
                ),
                "fields": (
                    "status",
                    "publish_at",
                    "author",
                    "is_featured",
                    ("reviewed_by", "reviewed_at"),
                    "review_note",
                    "preview_link",
                ),
            },
        ),
        SEO_FIELDSET,
    )

    # Champs que seules les personnes habilitées à publier peuvent modifier.
    PUBLISHER_FIELDS = ("publish_at", "is_featured", "author", "review_note")
    WORKFLOW = {
        "submit": workflow.submit_for_review,
        "publish": workflow.publish,
        "return_to_draft": workflow.return_to_draft,
        "archive": workflow.archive,
    }

    @admin.display(description="aperçu")
    def preview_link(self, obj):
        if not obj.pk:
            return "Disponible après le premier enregistrement."
        url = reverse("news:preview", args=[obj.preview_token])
        return format_html('<a href="{}" target="_blank" rel="noopener">Prévisualiser</a>', url)

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

    def response_change(self, request, obj):
        """Après l'enregistrement : action du circuit demandée par un bouton."""
        action = request.POST.get("_workflow")
        if action == "renew_preview":
            workflow.renew_preview_token(obj, request.user)
            self.message_user(
                request, "Nouveau lien de prévisualisation créé ; l'ancien ne fonctionne plus."
            )
            return HttpResponseRedirect(request.path)
        if action in self.WORKFLOW:
            try:
                if action == "return_to_draft":
                    workflow.return_to_draft(obj, request.user, obj.review_note)
                else:
                    self.WORKFLOW[action](obj, request.user)
            except (workflow.WorkflowError, PermissionDenied) as error:
                self.message_user(
                    request,
                    " ".join(error.messages if hasattr(error, "messages") else [str(error)]),
                    messages.ERROR,
                )
                return HttpResponseRedirect(request.path)
            self.message_user(
                request, f"Article « {obj.title} » : {obj.get_status_display().lower()}."
            )
            return HttpResponseRedirect(request.path)
        return super().response_change(request, obj)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        article = self.get_object(request, object_id)
        extra_context = {
            **(extra_context or {}),
            "workflow_actions": workflow.available_actions(article, request.user)
            if article
            else [],
        }
        return super().change_view(request, object_id, form_url, extra_context)

    @admin.action(description="Publier ou programmer les articles sélectionnés")
    def publish_selected(self, request, queryset):
        self._bulk(request, queryset, workflow.publish)

    @admin.action(description="Archiver les articles sélectionnés")
    def archive_selected(self, request, queryset):
        self._bulk(request, queryset, workflow.archive)

    def _bulk(self, request, queryset, action):
        done, refused = 0, []
        for article in queryset:
            try:
                action(article, request.user)
                done += 1
            except (workflow.WorkflowError, PermissionDenied):
                refused.append(article.title)
        self.message_user(request, f"{done} article(s) traité(s).")
        if refused:
            self.message_user(request, "Non traités : " + ", ".join(refused), messages.WARNING)
