from django.contrib import admin

from .models import ContactMessage, FaqItem


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "kind", "status", "created_at", "handled_by")
    list_filter = ("status", "kind")
    search_fields = ("subject", "name", "email", "organisation")
    date_hierarchy = "created_at"
    # Le message reçu n'est pas modifiable ; seul son suivi l'est. La pièce jointe
    # (privée) sera téléchargeable par une vue contrôlée à l'étape 14.
    readonly_fields = (
        "kind",
        "name",
        "email",
        "phone",
        "organisation",
        "subject",
        "message",
        "created_at",
    )
    fields = (*readonly_fields, "status", "handled_by")

    def has_add_permission(self, request):
        return False


@admin.register(FaqItem)
class FaqItemAdmin(admin.ModelAdmin):
    list_display = ("question", "category", "order", "is_published")
    list_filter = ("category", "is_published")
    list_editable = ("order", "is_published")
    search_fields = ("question", "answer")
