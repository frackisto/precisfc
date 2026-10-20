from django.contrib import admin

from .models import Payment, WebhookEvent


class ReadOnlyAdmin(admin.ModelAdmin):
    """Données financières : jamais créées ni modifiées à la main dans l'administration.

    La confirmation d'un paiement manuel passe par le tableau de bord (étape 13), qui
    vérifie le rôle de l'agent et trace l'opération.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(ReadOnlyAdmin):
    list_display = (
        "uuid",
        "created_at",
        "provider",
        "method",
        "amount",
        "status",
        "provider_reference",
        "confirmed_by",
    )
    list_filter = ("status", "provider", "method")
    search_fields = ("uuid", "provider_reference", "order__number", "booking__reference")
    date_hierarchy = "created_at"
    list_select_related = ("confirmed_by",)


@admin.register(WebhookEvent)
class WebhookEventAdmin(ReadOnlyAdmin):
    list_display = ("provider", "event_id", "received_at", "signature_valid", "processed_at")
    list_filter = ("provider", "signature_valid")
    search_fields = ("event_id",)
