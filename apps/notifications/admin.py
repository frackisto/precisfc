from django.contrib import admin

from .models import EmailLog, NewsletterCampaign, NewsletterSubscriber


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "is_confirmed", "confirmed_at", "unsubscribed_at", "source")
    list_filter = ("is_confirmed", "source")
    search_fields = ("email",)
    readonly_fields = ("is_confirmed", "confirmed_at", "unsubscribed_at", "user", "source")

    def has_add_permission(self, request):
        # Inscription uniquement par double confirmation (étape 7).
        return False


@admin.register(NewsletterCampaign)
class NewsletterCampaignAdmin(admin.ModelAdmin):
    list_display = ("subject", "status", "sent_count", "created_at")
    list_filter = ("status",)
    search_fields = ("subject",)


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "to", "subject", "template", "status")
    list_filter = ("status", "template")
    search_fields = ("to", "subject")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
