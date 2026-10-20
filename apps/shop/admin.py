from django.contrib import admin

from apps.core.admin import SEO_FIELDSET

from .models import (
    Product,
    ProductCategory,
    ProductImage,
    ProductVariant,
    StockMovement,
    WishlistItem,
)


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("__str__", "order")
    list_editable = ("order",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class ProductVariantInline(admin.TabularInline):
    """Le stock se modifie par des mouvements de stock (traçabilité), pas ici."""

    model = ProductVariant
    extra = 0
    readonly_fields = ("stock",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "base_price", "sale_price", "is_active", "is_featured")
    list_filter = ("category", "is_active", "is_featured")
    search_fields = ("name", "description", "variants__sku")
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ("category",)
    inlines = [ProductVariantInline, ProductImageInline]
    fieldsets = (
        (None, {"fields": ("category", "name", "slug", "description", "is_active", "is_featured")}),
        ("Prix", {"fields": ("base_price", "sale_price", ("sale_starts_at", "sale_ends_at"))}),
        SEO_FIELDSET,
    )


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("sku", "product", "size", "color", "stock", "low_stock_threshold", "is_active")
    list_filter = ("is_active", "product__category")
    search_fields = ("sku", "product__name")
    list_select_related = ("product",)
    readonly_fields = ("stock",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    """Journal : les mouvements ne se modifient ni ne se suppriment (service à l'étape 12)."""

    list_display = ("created_at", "variant", "delta", "reason", "user")
    list_filter = ("reason",)
    search_fields = ("variant__sku", "note")
    list_select_related = ("variant__product", "user")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "created_at")
    search_fields = ("user__email", "product__name")
    list_select_related = ("user", "product")
