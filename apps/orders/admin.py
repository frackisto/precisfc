from django.contrib import admin

from .models import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderStatusEvent,
    PromoCode,
    PromoRedemption,
    ReturnRequest,
    ShippingMethod,
)


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class CartItemInline(ReadOnlyInline):
    model = CartItem


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("__str__", "user", "updated_at")
    search_fields = ("user__email",)
    inlines = [CartItemInline]

    def has_add_permission(self, request):
        return False


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display = ("name", "zone_label", "fee", "free_above", "is_pickup", "is_active", "order")
    list_filter = ("is_active", "is_pickup")
    list_editable = ("order", "is_active")


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "kind",
        "value",
        "starts_at",
        "ends_at",
        "used_count",
        "max_uses",
        "is_active",
    )
    list_filter = ("kind", "is_active")
    search_fields = ("code",)
    readonly_fields = ("used_count",)


class OrderItemInline(ReadOnlyInline):
    model = OrderItem


class OrderStatusEventInline(ReadOnlyInline):
    model = OrderStatusEvent


class PromoRedemptionInline(ReadOnlyInline):
    model = PromoRedemption


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Consultation des commandes : création et changements de statut passent par les
    services de commande (étape 12), qui tiennent stock, paiements et historique à jour."""

    list_display = ("number", "created_at", "email", "status", "total", "paid_at")
    list_filter = ("status", "shipping_method")
    search_fields = ("number", "email", "invoice_number", "shipping_full_name")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline, OrderStatusEventInline, PromoRedemptionInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ("__str__", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("order__number",)
    filter_horizontal = ("items",)
