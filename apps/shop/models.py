from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import SEOFields, SluggedModel, TimeStampedModel

MONEY = {"max_digits": 12, "decimal_places": 2, "validators": [MinValueValidator(0)]}


class ProductCategory(SluggedModel):
    name = models.CharField("nom", max_length=100)
    parent = models.ForeignKey(
        "self",
        verbose_name="catégorie parente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    image = models.ImageField("image", upload_to="shop/categories/", blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "catégorie de produits"
        verbose_name_plural = "catégories de produits"
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.parent} › {self.name}" if self.parent_id else self.name


class Product(SluggedModel, SEOFields):
    category = models.ForeignKey(
        ProductCategory, verbose_name="catégorie", on_delete=models.PROTECT, related_name="products"
    )
    name = models.CharField("nom", max_length=200)
    description = models.TextField("description", blank=True)
    base_price = models.DecimalField("prix (FCFA)", **MONEY)
    sale_price = models.DecimalField("prix promotionnel (FCFA)", null=True, blank=True, **MONEY)
    sale_starts_at = models.DateTimeField("début de la promotion", null=True, blank=True)
    sale_ends_at = models.DateTimeField("fin de la promotion", null=True, blank=True)
    is_active = models.BooleanField("en vente", default=True)
    is_featured = models.BooleanField("mis en avant", default=False)

    class Meta:
        verbose_name = "produit"
        verbose_name_plural = "produits"
        ordering = ["name"]
        indexes = [models.Index(fields=["is_active", "is_featured"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(base_price__gte=0), name="shop_product_base_price_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(sale_price__isnull=True)
                | models.Q(sale_price__gte=0, sale_price__lt=models.F("base_price")),
                name="shop_product_sale_below_base",
                violation_error_message="Le prix promotionnel doit être inférieur au prix normal.",
            ),
            models.CheckConstraint(
                condition=models.Q(sale_starts_at__isnull=True)
                | models.Q(sale_ends_at__isnull=True)
                | models.Q(sale_ends_at__gt=models.F("sale_starts_at")),
                name="shop_product_sale_ends_after_start",
                violation_error_message="La fin de la promotion doit suivre son début.",
            ),
        ]

    def __str__(self):
        return self.name


class ProductImage(TimeStampedModel):
    product = models.ForeignKey(
        Product, verbose_name="produit", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField("image", upload_to="shop/products/")
    alt_text = models.CharField("texte alternatif", max_length=255, blank=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)
    color = models.CharField(
        "couleur", max_length=50, blank=True, help_text="Image propre à une couleur de variante."
    )

    class Meta:
        verbose_name = "image de produit"
        verbose_name_plural = "images de produit"
        ordering = ["order", "pk"]

    def __str__(self):
        return self.alt_text or f"Image de {self.product}"


class ProductVariant(TimeStampedModel):
    product = models.ForeignKey(
        Product, verbose_name="produit", on_delete=models.CASCADE, related_name="variants"
    )
    sku = models.CharField("référence (SKU)", max_length=64, unique=True)
    size = models.CharField("taille", max_length=20, blank=True)
    color = models.CharField("couleur", max_length=50, blank=True)
    price_override = models.DecimalField("prix spécifique (FCFA)", null=True, blank=True, **MONEY)
    # Non signé en base : le stock ne peut jamais devenir négatif (pas de survente).
    stock = models.PositiveIntegerField("stock", default=0)
    low_stock_threshold = models.PositiveIntegerField("seuil d'alerte", default=3)
    is_active = models.BooleanField("active", default=True)

    class Meta:
        verbose_name = "variante"
        verbose_name_plural = "variantes"
        ordering = ["product", "size", "color"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "size", "color"],
                name="shop_variant_unique_size_color",
                violation_error_message="Cette taille et cette couleur existent déjà.",
            ),
        ]

    def __str__(self):
        details = " / ".join(part for part in (self.size, self.color) if part)
        return f"{self.product} ({details})" if details else str(self.product)


class StockMovement(TimeStampedModel):
    """Journal des entrées et sorties de stock (jamais modifié après coup)."""

    class Reason(models.TextChoices):
        PURCHASE = "PURCHASE", "Vente"
        CANCEL = "CANCEL", "Annulation de commande"
        RETURN = "RETURN", "Retour client"
        ADJUSTMENT = "ADJUSTMENT", "Ajustement d'inventaire"
        RESTOCK = "RESTOCK", "Réapprovisionnement"

    variant = models.ForeignKey(
        ProductVariant, verbose_name="variante", on_delete=models.PROTECT, related_name="movements"
    )
    delta = models.IntegerField("variation")
    reason = models.CharField("motif", max_length=10, choices=Reason.choices)
    order_item = models.ForeignKey(
        "orders.OrderItem",
        verbose_name="ligne de commande",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    note = models.CharField("remarque", max_length=255, blank=True)

    class Meta:
        verbose_name = "mouvement de stock"
        verbose_name_plural = "mouvements de stock"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(delta=0), name="shop_stockmovement_delta_not_zero"
            ),
        ]

    def __str__(self):
        return f"{self.variant} : {self.delta:+d} ({self.get_reason_display()})"


class WishlistItem(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="utilisateur",
        on_delete=models.CASCADE,
        related_name="wishlist",
    )
    product = models.ForeignKey(
        Product, verbose_name="produit", on_delete=models.CASCADE, related_name="wishlisted_by"
    )

    class Meta:
        verbose_name = "favori"
        verbose_name_plural = "listes de souhaits"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="shop_wishlist_unique"),
        ]

    def __str__(self):
        return f"{self.user} ♥ {self.product}"
