"""Billetterie : catégories, réservations et billets."""

from decimal import Decimal

import pytest

from apps.ticketing.models import Booking, Ticket, TicketCategory
from tests.factories import BookingFactory, MatchFactory, UserFactory
from tests.helpers import rejected_by_database

pytestmark = pytest.mark.django_db


def make_category(match=None, **kwargs):
    values = {"name": "Tribune populaire", "price": Decimal("2000"), "capacity": 500}
    return TicketCategory.objects.create(match=match or MatchFactory(), **{**values, **kwargs})


def test_category_needs_at_least_one_seat():
    with rejected_by_database():
        make_category(capacity=0)


def test_category_name_is_unique_per_match():
    category = make_category()

    with rejected_by_database():
        make_category(match=category.match)


def test_pending_booking_must_expire():
    with rejected_by_database():
        Booking.objects.create(
            reference="RES-1", user=UserFactory(), match=MatchFactory(), total=Decimal("2000")
        )


def test_each_ticket_gets_a_unique_unpredictable_code():
    booking = BookingFactory()
    category = make_category(match=booking.match)

    first = Ticket.objects.create(booking=booking, category=category, holder_name="Awa")
    second = Ticket.objects.create(booking=booking, category=category, holder_name="Koffi")

    assert first.code != second.code
    assert first.code.version == 4


def test_used_ticket_must_have_a_usage_date():
    booking = BookingFactory()

    with rejected_by_database():
        Ticket.objects.create(
            booking=booking,
            category=make_category(match=booking.match),
            holder_name="Awa",
            status=Ticket.Status.USED,
        )


def test_match_with_ticket_categories_cannot_be_deleted():
    category = make_category()

    with rejected_by_database():
        category.match.delete()
