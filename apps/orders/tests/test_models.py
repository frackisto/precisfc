"""Commandes : cohérence des montants, codes promo, paniers."""

from decimal import Decimal

import pytest
from django.db.models import F

from apps.orders.models import Cart, OrderItem, PromoCode
from tests.factories import OrderFactory, ProductVariantFactory
from tests.helpers import rejected_by_database

pytestmark = pytest.mark.django_db


def test_order_total_must_equal_subtotal_minus_discount_plus_shipping():
    with rejected_by_database():
        OrderFactory(
            subtotal=Decimal("15000"), shipping_fee=Decimal("2000"), total=Decimal("15000")
        )


def test_consistent_order_is_accepted_in_fcfa():
    order = OrderFactory(
        subtotal=Decimal("30000"),
        discount=Decimal("3000"),
        shipping_fee=Decimal("2000"),
        total=Decimal("29000"),
    )

    assert order.currency == "XOF"


def test_discount_cannot_exceed_subtotal():
    with rejected_by_database():
        OrderFactory(
            subtotal=Decimal("5000"),
            discount=Decimal("6000"),
            shipping_fee=Decimal("2000"),
            total=Decimal("1000"),
        )


def test_order_number_is_unique():
    OrderFactory(number="CMD-000001")

    with rejected_by_database():
        OrderFactory(number="CMD-000001")


def test_order_line_total_is_unit_price_times_quantity():
    order = OrderFactory()
    variant = ProductVariantFactory()

    with rejected_by_database():
        OrderItem.objects.create(
            order=order,
            variant=variant,
            product_name="Maillot",
            sku=variant.sku,
            unit_price=Decimal("15000"),
            quantity=2,
            line_total=Decimal("15000"),
        )


def test_promo_code_is_stored_uppercase_and_unique_regardless_of_case():
    promo = PromoCode.objects.create(code=" bienvenue10 ", kind="PERCENT", value=10)

    assert promo.code == "BIENVENUE10"
    with rejected_by_database():
        PromoCode.objects.bulk_create([PromoCode(code="Bienvenue10", kind="PERCENT", value=10)])


@pytest.mark.parametrize(("kind", "value"), [("PERCENT", 0), ("PERCENT", 150), ("FIXED", 0)])
def test_promo_code_value_must_make_sense(kind, value):
    with rejected_by_database():
        PromoCode.objects.create(code="ERREUR", kind=kind, value=value)


def test_promo_code_cannot_be_used_beyond_its_limit():
    promo = PromoCode.objects.create(code="LIMITE", kind="FIXED", value=1000, max_uses=1)
    PromoCode.objects.filter(pk=promo.pk).update(used_count=F("used_count") + 1)

    with rejected_by_database():
        PromoCode.objects.filter(pk=promo.pk).update(used_count=F("used_count") + 1)


def test_cart_belongs_to_a_user_or_a_session():
    Cart.objects.create(session_key="a" * 32)

    with rejected_by_database():
        Cart.objects.create()
