"""Boutique : prix, promotions et stock."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db.models import F
from django.utils import timezone

from apps.shop.models import ProductVariant, StockMovement, WishlistItem
from tests.factories import ProductFactory, ProductVariantFactory, UserFactory
from tests.helpers import rejected_by_database

pytestmark = pytest.mark.django_db


def test_sale_price_must_be_below_base_price():
    with rejected_by_database():
        ProductFactory(base_price=Decimal("15000"), sale_price=Decimal("15000"))


def test_valid_sale_price_is_accepted():
    product = ProductFactory(base_price=Decimal("15000"), sale_price=Decimal("12000"))

    assert product.sale_price == Decimal("12000")


def test_sale_must_end_after_it_starts():
    now = timezone.now()

    with rejected_by_database():
        ProductFactory(
            sale_price=Decimal("10000"), sale_starts_at=now, sale_ends_at=now - timedelta(days=1)
        )


def test_stock_can_never_become_negative():
    variant = ProductVariantFactory(stock=2)

    with rejected_by_database():
        ProductVariant.objects.filter(pk=variant.pk).update(stock=F("stock") - 3)

    variant.refresh_from_db()
    assert variant.stock == 2


def test_sku_is_unique():
    ProductVariantFactory(sku="MAI-DOM-M")

    with rejected_by_database():
        ProductVariantFactory(sku="MAI-DOM-M")


def test_size_and_colour_are_unique_per_product():
    variant = ProductVariantFactory(size="L", color="Bleu")

    with rejected_by_database():
        ProductVariantFactory(product=variant.product, size="L", color="Bleu")


def test_stock_movement_cannot_be_zero():
    with rejected_by_database():
        StockMovement.objects.create(
            variant=ProductVariantFactory(), delta=0, reason=StockMovement.Reason.ADJUSTMENT
        )


def test_variant_with_stock_history_cannot_be_deleted():
    variant = ProductVariantFactory()
    StockMovement.objects.create(variant=variant, delta=5, reason=StockMovement.Reason.RESTOCK)

    with rejected_by_database():
        variant.delete()


def test_product_is_wishlisted_once_per_user():
    user, product = UserFactory(), ProductFactory()
    WishlistItem.objects.create(user=user, product=product)

    with rejected_by_database():
        WishlistItem.objects.create(user=user, product=product)
