"""Rapport financier : période, détail des paiements et export CSV."""

import csv
import io
from datetime import date, datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.dashboard.exports import safe_cell
from apps.dashboard.forms import PeriodForm
from apps.dashboard.indicators import Period
from tests.factories import BookingFactory, OrderFactory, PaymentFactory

pytestmark = pytest.mark.django_db

FINANCES = reverse("dashboard:finances")
EXPORT = reverse("dashboard:finances_export")
NBSP = chr(0xA0)


def at(*args):
    return timezone.make_aware(datetime(*args))


@pytest.fixture
def treasurer(login):
    return login("treasurer")


def test_period_defaults_to_the_current_month():
    today = timezone.localdate()

    assert PeriodForm().period == Period(today.replace(day=1), today)
    assert PeriodForm({}).period == Period(today.replace(day=1), today)


def test_period_with_only_a_start_runs_until_today():
    form = PeriodForm({"du": "2026-01-01"})

    assert form.period == Period(date(2026, 1, 1), timezone.localdate())


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"du": "2026-10-10", "au": "2026-10-01"}, "doit suivre"),
        ({"du": "2020-01-01", "au": "2026-10-01"}, "trois ans"),
        ({"du": "pas-une-date"}, "date valide"),
    ],
)
def test_invalid_period_falls_back_to_the_current_month(treasurer, data, message):
    response = treasurer.get(FINANCES, data)

    assert response.status_code == 200
    assert message in response.content.decode()
    today = timezone.localdate()
    assert response.context["period"] == Period(today.replace(day=1), today)


def test_report_for_a_chosen_period(treasurer):
    PaymentFactory(amount=Decimal("17000"), confirmed_at=at(2026, 3, 2, 10))
    PaymentFactory(
        order=None,
        booking=BookingFactory(reference="RES-000777"),
        amount=Decimal("5000"),
        method="MOBILE_MONEY_MANUAL",
        provider_reference="MP2603.1234",
        confirmed_at=at(2026, 3, 31, 23, 59),
    )
    PaymentFactory(amount=Decimal("99000"), confirmed_at=at(2026, 4, 1))

    response = treasurer.get(FINANCES, {"du": "2026-03-01", "au": "2026-03-31"})

    page = response.content.decode()
    assert response.context["revenue"].total == Decimal("22000")
    assert f"22{NBSP}000{NBSP}FCFA" in page
    assert "RES-000777" in page
    assert "MP2603.1234" in page
    # Le paiement d'avril n'est que dans l'évolution sur 12 mois, pas dans le détail.
    assert len(response.context["payments"]) == 2
    assert [row["method"] for row in response.context["by_method"]] == [
        "CASH",
        "MOBILE_MONEY_MANUAL",
    ]
    assert f"{EXPORT}?du=2026-03-01&amp;au=2026-03-31" in page


def test_report_shows_presets_and_fills_the_form_with_the_current_month(treasurer):
    response = treasurer.get(FINANCES)
    page = response.content.decode()
    today = timezone.localdate()

    assert f'value="{today.replace(day=1).isoformat()}"' in page
    assert f'value="{today.isoformat()}"' in page
    assert "12 derniers mois" in page


def read_csv(response):
    text = response.content.decode("utf-8")
    assert text.startswith(chr(0xFEFF))
    return list(csv.reader(io.StringIO(text[1:]), delimiter=";"))


def test_csv_export(treasurer, make_user):
    confirmer = make_user("treasurer", email="caisse@precisfc.test")
    order = OrderFactory(number="CMD-000042")
    PaymentFactory(
        order=order,
        amount=Decimal("17000"),
        confirmed_at=at(2026, 3, 2, 10, 30),
        confirmed_by=confirmer,
    )
    PaymentFactory(amount=Decimal("1"), status="PENDING", confirmed_at=None)
    PaymentFactory(amount=Decimal("1"), confirmed_at=at(2026, 4, 1))

    response = treasurer.get(EXPORT, {"du": "2026-03-01", "au": "2026-03-31"})

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert response["Content-Disposition"] == (
        'attachment; filename="paiements-20260301-20260331.csv"'
    )
    header, *rows = read_csv(response)
    assert header[0] == "Date de confirmation"
    assert len(rows) == 1
    row = rows[0]
    assert row[0] == "02/03/2026 10:30"
    assert row[2] == "Commande CMD-000042"
    assert row[3] == "Espèces"
    assert row[6] == "17000"
    assert row[7] == "caisse@precisfc.test"


def test_csv_export_neutralises_spreadsheet_formulas(treasurer):
    PaymentFactory(
        order=OrderFactory(number="=HYPERLINK(1)"),
        provider_reference='=CMD|" /C calc"!A0',
        confirmed_at=timezone.now(),
    )

    _, row = read_csv(treasurer.get(EXPORT))

    assert row[2] == "Commande =HYPERLINK(1)"  # ne commence pas par « = » : sans danger
    assert row[5] == '\'=CMD|" /C calc"!A0'


@pytest.mark.parametrize("value", ["=1+1", "+1", "-1", "@SUM(A1)", chr(9) + "x", chr(13) + "x"])
def test_safe_cell_prefixes_formulas(value):
    assert safe_cell(value) == "'" + value


@pytest.mark.parametrize("value", ["Commande 12", "17000", "", None])
def test_safe_cell_keeps_ordinary_values(value):
    assert safe_cell(value) == ("" if value is None else value)


def test_invalid_export_period_is_refused(treasurer):
    response = treasurer.get(EXPORT, {"du": "2026-10-10", "au": "2026-10-01"})

    assert response.status_code == 302
    assert response["Location"] == FINANCES


def test_shop_manager_cannot_export_payments(login):
    assert login("shop_manager").get(EXPORT).status_code == 403


def test_csv_export_describes_ticketing_payments(treasurer):
    booking = BookingFactory(reference="RES-000321")
    PaymentFactory(order=None, booking=booking, amount=Decimal("5000"), confirmed_at=timezone.now())

    _, row = read_csv(treasurer.get(EXPORT))

    match = booking.match
    assert row[2] == f"Billetterie RES-000321 ({match.home_club} - {match.away_club})"
    assert row[6] == "5000"
    assert row[7] == ""
