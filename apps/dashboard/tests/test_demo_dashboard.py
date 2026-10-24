"""Commande demo_dashboard : données cohérentes, comptes par rôle, suppression ciblée."""

from decimal import Decimal

import pytest
from django.core.management import CommandError, call_command
from django.db.models import Sum
from django.urls import reverse

from apps.accounts.models import User
from apps.dashboard import indicators
from apps.dashboard.management.commands.demo_dashboard import ACCOUNTS, DEMO_DOMAIN
from apps.news.management.commands.demo_news import DEMO_PASSWORD
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.ticketing.models import Booking, Ticket
from tests.factories import OrderFactory, PaymentFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def debug(settings):
    settings.DEBUG = True


def test_refused_outside_development(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError, match="développement"):
        call_command("demo_dashboard", verbosity=0)


def test_creates_consistent_shop_and_payment_data(debug):
    call_command("demo_dashboard", verbosity=0)

    assert Order.objects.filter(number__startswith="DEMO-").count() > 40
    # Chaque statut utile au tableau de bord est représenté.
    assert set(Payment.objects.values_list("status", flat=True)) >= {
        "SUCCEEDED",
        "PENDING",
        "INITIATED",
        "FAILED",
        "REFUNDED",
    }
    year = indicators.last_twelve_months()
    expected = Payment.objects.filter(status="SUCCEEDED").aggregate(total=Sum("amount"))["total"]
    assert indicators.revenue(year).total == expected
    assert indicators.pending_manual_payments()["count"] == 3
    assert indicators.orders_overview()["to_prepare"] == 3
    assert indicators.out_of_stock() == {"products": 1, "variants": 1}
    assert indicators.low_stock_variants().count() == 2
    assert indicators.application_counts()["retention_overdue"] == 1
    assert indicators.contact_counts()["new"] == 2
    assert indicators.newsletter_subscribers_count() == 5
    # Aucune billetterie sans la saison de démonstration.
    assert not Booking.objects.exists()


def test_ticketing_uses_the_demo_season(debug):
    call_command("demo_season", verbosity=0)
    call_command("demo_dashboard", verbosity=0)

    sales = indicators.ticket_sales()
    assert sales
    sale = sales[0]
    assert 0 < sale.sold < sale.capacity
    assert sale.reserved == 6
    assert sale.revenue > 0
    sold = Ticket.objects.filter(booking__status="CONFIRMED").count()
    assert indicators.tickets_sold(indicators.this_month())["total"] == sold
    # La suppression de la saison emporte sa billetterie (sinon clés protégées).
    call_command("demo_season", "--delete", verbosity=0)
    assert not Booking.objects.exists()


def test_demo_accounts_open_their_pages(debug, client):
    call_command("demo_dashboard", verbosity=0)
    call_command("setup_roles", verbosity=0)

    for email, _key, _name in ACCOUNTS:
        assert User.objects.get(email=email).has_perm("core.view_dashboard")
    response = client.post(
        reverse("account_login"),
        {"login": f"tresorier@{DEMO_DOMAIN}", "password": DEMO_PASSWORD},
    )
    assert response.status_code == 302
    assert client.get(reverse("dashboard:finances")).status_code == 200
    assert client.get(reverse("dashboard:scores")).status_code == 403


def test_running_twice_does_not_duplicate(debug):
    call_command("demo_dashboard", verbosity=0)
    first = (Order.objects.count(), Payment.objects.count(), User.objects.count())
    call_command("demo_dashboard", verbosity=0)

    assert (Order.objects.count(), Payment.objects.count(), User.objects.count()) == first


def test_delete_keeps_real_data(debug):
    real_user = UserFactory(email="vrai@precisfc.test")
    real_payment = PaymentFactory(order=OrderFactory(number="CMD-000001"), amount=Decimal("1000"))
    call_command("demo_dashboard", verbosity=0)

    call_command("demo_dashboard", "--delete", verbosity=0)

    assert list(Payment.objects.all()) == [real_payment]
    assert list(Order.objects.all()) == [real_payment.order]
    assert list(User.objects.all()) == [real_user]


def test_demo_news_accounts_are_untouched(debug, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    call_command("demo_news", verbosity=0)
    call_command("demo_dashboard", verbosity=0)

    call_command("demo_dashboard", "--delete", verbosity=0)
    assert User.objects.filter(email__endswith="@demo.precisfc.test").count() == 2
    call_command("demo_dashboard", verbosity=0)
    call_command("demo_news", "--delete", verbosity=0)
    assert User.objects.filter(email__endswith=f"@{DEMO_DOMAIN}").count() == 5
