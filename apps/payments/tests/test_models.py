"""Paiements : rattachement, références de transaction, confirmation."""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.payments.models import Payment, WebhookEvent
from tests.factories import BookingFactory, OrderFactory
from tests.helpers import rejected_by_database

pytestmark = pytest.mark.django_db

MANUAL = {"provider": "MANUAL", "method": "MOBILE_MONEY_MANUAL", "amount": Decimal("17000")}


def test_payment_targets_an_order_or_a_booking_but_not_both():
    Payment.objects.create(order=OrderFactory(), **MANUAL)
    Payment.objects.create(booking=BookingFactory(), **MANUAL)

    with rejected_by_database():
        Payment.objects.create(**MANUAL)
    with rejected_by_database():
        Payment.objects.create(order=OrderFactory(), booking=BookingFactory(), **MANUAL)


def test_mobile_money_reference_cannot_validate_two_payments():
    Payment.objects.create(
        order=OrderFactory(), provider_reference="MP261019.1234.A00001", **MANUAL
    )

    with rejected_by_database():
        Payment.objects.create(
            order=OrderFactory(), provider_reference="MP261019.1234.A00001", **MANUAL
        )


def test_payments_without_reference_do_not_conflict():
    Payment.objects.create(order=OrderFactory(), **MANUAL)
    Payment.objects.create(order=OrderFactory(), **MANUAL)

    assert Payment.objects.filter(provider_reference__isnull=True).count() == 2


def test_succeeded_payment_must_be_confirmed():
    with rejected_by_database():
        Payment.objects.create(order=OrderFactory(), status="SUCCEEDED", **MANUAL)

    payment = Payment.objects.create(
        order=OrderFactory(), status="SUCCEEDED", confirmed_at=timezone.now(), **MANUAL
    )
    assert payment.currency == "XOF"


def test_amount_must_be_positive():
    with rejected_by_database():
        Payment.objects.create(order=OrderFactory(), **{**MANUAL, "amount": Decimal("0")})


def test_order_with_payments_cannot_be_deleted():
    order = OrderFactory()
    Payment.objects.create(order=order, **MANUAL)

    with rejected_by_database():
        order.delete()


def test_webhook_event_is_recorded_once():
    WebhookEvent.objects.create(provider="AGREGATEUR", event_id="evt_1", payload={})

    with rejected_by_database():
        WebhookEvent.objects.create(provider="AGREGATEUR", event_id="evt_1", payload={})
