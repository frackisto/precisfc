from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField

from apps.core.models import TimeStampedModel

MONEY = {"max_digits": 12, "decimal_places": 2, "validators": [MinValueValidator(0)]}


class Cart(TimeStampedModel):
    """Panier d'un supporter connecté ou d'un invité (identifié par sa session)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="utilisateur",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart",
    )
    session_key = models.CharField(
        "session", max_length=40, unique=True, null=True, blank=True, editable=False
    )

    class Meta:
        verbose_name = "panier"
        verbose_name_plural = "paniers"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(user__isnull=False) | models.Q(session_key__isnull=False),
                name="orders_cart_has_owner",
            ),
        ]

    def __str__(self):
        return f"Panier de {self.user}" if self.user_id else f"Panier invité {self.pk}"


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(
        Cart, verbose_name="panier", on_delete=models.CASCADE, related_name="items"
    )
    variant = models.ForeignKey(
        "shop.ProductVariant", verbose_name="article", on_delete=models.CASCADE, related_name="+"
    )
    quantity = models.PositiveSmallIntegerField(
        "quantité", default=1, validators=[MinValueValidator(1)]
    )

    class Meta:
        verbose_name = "article du panier"
        verbose_name_plural = "articles du panier"
        constraints = [
            models.UniqueConstraint(fields=["cart", "variant"], name="orders_cartitem_unique"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="orders_cartitem_quantity_positive"
            ),
        ]

    def __str__(self):
        return f"{self.quantity} × {self.variant}"


class ShippingMethod(TimeStampedModel):
    name = models.CharField("nom", max_length=100)
    description = models.CharField("description", max_length=255, blank=True)
    zone_label = models.CharField(
        "zone", max_length=100, help_text="Ex. Abidjan, intérieur du pays."
    )
    fee = models.DecimalField("frais (FCFA)", **MONEY)
    free_above = models.DecimalField("gratuit à partir de (FCFA)", null=True, blank=True, **MONEY)
    delivery_days = models.PositiveSmallIntegerField("délai (jours)", null=True, blank=True)
    is_pickup = models.BooleanField("retrait au club", default=False)
    is_active = models.BooleanField("actif", default=True)
    order = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "mode de livraison"
        verbose_name_plural = "modes de livraison"
        ordering = ["order", "fee"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fee__gte=0), name="orders_shipping_fee_positive"
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.zone_label})"


class PromoCode(TimeStampedModel):
    class Kind(models.TextChoices):
        PERCENT = "PERCENT", "Pourcentage"
        FIXED = "FIXED", "Montant fixe"
        FREE_SHIPPING = "FREE_SHIPPING", "Livraison offerte"

    # Unicité insensible à la casse grâce à la collation utf8mb4_unicode_ci.
    code = models.CharField("code", max_length=50, unique=True)
    kind = models.CharField("type", max_length=15, choices=Kind.choices)
    value = models.DecimalField(
        "valeur", max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    min_subtotal = models.DecimalField("montant minimum (FCFA)", default=0, **MONEY)
    starts_at = models.DateTimeField("début de validité", null=True, blank=True)
    ends_at = models.DateTimeField("fin de validité", null=True, blank=True)
    max_uses = models.PositiveIntegerField("utilisations maximum", null=True, blank=True)
    max_uses_per_user = models.PositiveIntegerField(
        "utilisations maximum par client", null=True, blank=True
    )
    used_count = models.PositiveIntegerField("utilisations", default=0, editable=False)
    is_active = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "code promo"
        verbose_name_plural = "codes promo"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(kind="PERCENT") | models.Q(value__gt=0, value__lte=100),
                name="orders_promo_percent_range",
                violation_error_message="Un pourcentage doit être compris entre 1 et 100.",
            ),
            models.CheckConstraint(
                condition=~models.Q(kind="FIXED") | models.Q(value__gt=0),
                name="orders_promo_fixed_positive",
                violation_error_message="Le montant de la réduction doit être positif.",
            ),
            models.CheckConstraint(
                condition=models.Q(starts_at__isnull=True)
                | models.Q(ends_at__isnull=True)
                | models.Q(ends_at__gt=models.F("starts_at")),
                name="orders_promo_ends_after_start",
                violation_error_message="La fin de validité doit suivre son début.",
            ),
            # Dernier rempart contre le dépassement en cas d'utilisations simultanées.
            models.CheckConstraint(
                condition=models.Q(max_uses__isnull=True)
                | models.Q(used_count__lte=models.F("max_uses")),
                name="orders_promo_used_within_limit",
            ),
        ]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "PENDING_PAYMENT", "En attente de paiement"
        PAID = "PAID", "Payée"
        PROCESSING = "PROCESSING", "En préparation"
        SHIPPED = "SHIPPED", "Expédiée"
        DELIVERED = "DELIVERED", "Livrée"
        CANCELLED = "CANCELLED", "Annulée"
        REFUNDED = "REFUNDED", "Remboursée"

    number = models.CharField("numéro", max_length=20, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    email = models.EmailField("e-mail")
    phone = PhoneNumberField("téléphone")
    # Instantané de l'adresse : la commande reste exacte si le client modifie son carnet.
    shipping_full_name = models.CharField("destinataire", max_length=150)
    shipping_phone = PhoneNumberField("téléphone du destinataire", blank=True)
    shipping_line1 = models.CharField("adresse", max_length=255, blank=True)
    shipping_line2 = models.CharField("complément d'adresse", max_length=255, blank=True)
    shipping_commune = models.CharField("commune", max_length=100, blank=True)
    shipping_city = models.CharField("ville", max_length=100, blank=True)
    shipping_country = CountryField("pays", default="CI")
    shipping_method = models.ForeignKey(
        ShippingMethod,
        verbose_name="mode de livraison",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        "statut", max_length=15, choices=Status.choices, default=Status.PENDING_PAYMENT
    )
    subtotal = models.DecimalField("sous-total", **MONEY)
    discount = models.DecimalField("réduction", default=0, **MONEY)
    shipping_fee = models.DecimalField("frais de livraison", default=0, **MONEY)
    total = models.DecimalField("total", **MONEY)
    currency = models.CharField("devise", max_length=3, default="XOF", editable=False)
    promo_code = models.ForeignKey(
        PromoCode,
        verbose_name="code promo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    invoice_number = models.CharField(
        "numéro de facture", max_length=20, unique=True, null=True, blank=True
    )
    paid_at = models.DateTimeField("payée le", null=True, blank=True)
    tracking_number = models.CharField("numéro de suivi", max_length=100, blank=True)
    expires_at = models.DateTimeField("expire le", null=True, blank=True)

    class Meta:
        verbose_name = "commande"
        verbose_name_plural = "commandes"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "expires_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    subtotal__gte=0, discount__gte=0, shipping_fee__gte=0, total__gte=0
                ),
                name="orders_order_amounts_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(discount__lte=models.F("subtotal")),
                name="orders_order_discount_le_subtotal",
                violation_error_message="La réduction ne peut dépasser le sous-total.",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    total=models.F("subtotal") - models.F("discount") + models.F("shipping_fee")
                ),
                name="orders_order_total_consistent",
                violation_error_message="Total incohérent : sous-total − réduction + livraison.",
            ),
        ]

    def __str__(self):
        return self.number


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(
        Order, verbose_name="commande", on_delete=models.CASCADE, related_name="items"
    )
    variant = models.ForeignKey(
        "shop.ProductVariant",
        verbose_name="variante",
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    # Instantané au moment de la commande.
    product_name = models.CharField("produit", max_length=200)
    sku = models.CharField("référence", max_length=64)
    size = models.CharField("taille", max_length=20, blank=True)
    color = models.CharField("couleur", max_length=50, blank=True)
    unit_price = models.DecimalField("prix unitaire", **MONEY)
    quantity = models.PositiveSmallIntegerField("quantité", validators=[MinValueValidator(1)])
    line_total = models.DecimalField("total de la ligne", **MONEY)

    class Meta:
        verbose_name = "ligne de commande"
        verbose_name_plural = "lignes de commande"
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="orders_orderitem_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(line_total=models.F("unit_price") * models.F("quantity")),
                name="orders_orderitem_line_total_consistent",
                violation_error_message="Total de ligne incohérent : prix unitaire × quantité.",
            ),
        ]

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"


class OrderStatusEvent(TimeStampedModel):
    """Historique des changements de statut d'une commande."""

    order = models.ForeignKey(
        Order, verbose_name="commande", on_delete=models.CASCADE, related_name="status_events"
    )
    from_status = models.CharField(
        "ancien statut", max_length=15, choices=Order.Status.choices, blank=True
    )
    to_status = models.CharField("nouveau statut", max_length=15, choices=Order.Status.choices)
    note = models.CharField("remarque", max_length=255, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "changement de statut"
        verbose_name_plural = "historique des statuts"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.order} : {self.from_status or '—'} → {self.to_status}"


class ReturnRequest(TimeStampedModel):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Demandé"
        ACCEPTED = "ACCEPTED", "Accepté"
        REJECTED = "REJECTED", "Refusé"
        RECEIVED = "RECEIVED", "Articles reçus"
        REFUNDED = "REFUNDED", "Remboursé"

    order = models.ForeignKey(
        Order, verbose_name="commande", on_delete=models.PROTECT, related_name="return_requests"
    )
    items = models.ManyToManyField(
        OrderItem, verbose_name="articles", related_name="return_requests"
    )
    reason = models.TextField("motif")
    status = models.CharField(
        "statut", max_length=10, choices=Status.choices, default=Status.REQUESTED
    )
    resolution_note = models.TextField("décision", blank=True)

    class Meta:
        verbose_name = "demande de retour"
        verbose_name_plural = "demandes de retour"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Retour {self.pk} — {self.order}"


class PromoRedemption(TimeStampedModel):
    promo = models.ForeignKey(
        PromoCode, verbose_name="code promo", on_delete=models.PROTECT, related_name="redemptions"
    )
    order = models.ForeignKey(
        Order, verbose_name="commande", on_delete=models.CASCADE, related_name="promo_redemptions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "utilisation de code promo"
        verbose_name_plural = "utilisations de codes promo"
        constraints = [
            models.UniqueConstraint(fields=["promo", "order"], name="orders_redemption_unique"),
        ]

    def __str__(self):
        return f"{self.promo} — {self.order}"
