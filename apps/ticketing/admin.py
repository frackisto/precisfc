from django.contrib import admin

from .models import Booking, Ticket, TicketCategory, TicketScan


@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "match", "price", "capacity", "max_per_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "match__home_club__name", "match__away_club__name")
    autocomplete_fields = ("match",)


class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0
    can_delete = False
    fields = ("holder_name", "category", "code", "status", "used_at", "gate")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Consultation : réservations, annulations et contrôles passent par les services
    de billetterie (étape 13), qui verrouillent les quotas."""

    list_display = ("reference", "user", "match", "status", "total", "expires_at", "created_at")
    list_filter = ("status",)
    search_fields = ("reference", "user__email")
    list_select_related = ("user", "match__home_club", "match__away_club")
    inlines = [TicketInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TicketScan)
class TicketScanAdmin(admin.ModelAdmin):
    list_display = ("scanned_at", "result", "ticket", "agent", "gate")
    list_filter = ("result", "gate")
    search_fields = ("raw_code",)
    date_hierarchy = "scanned_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
