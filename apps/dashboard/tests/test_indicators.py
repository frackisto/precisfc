"""Exactitude des indicateurs : chaque chiffre est vérifié sur un jeu de données connu,
cas limites compris (bornes de période, statuts exclus, seuils)."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.academy.models import Application
from apps.accounts.models import User
from apps.competitions.models import Club
from apps.contact.models import ContactMessage
from apps.dashboard import indicators
from apps.dashboard.indicators import Period
from apps.matches.models import Match
from apps.news.models import Article
from apps.notifications.models import NewsletterSubscriber
from apps.orders.models import Order, OrderItem, ReturnRequest
from apps.payments.models import Payment
from apps.teams.models import Staff
from apps.ticketing.models import Booking, Ticket
from tests.factories import (
    ApplicationFactory,
    BookingFactory,
    ClubFactory,
    CompetitionSeasonFactory,
    MatchFactory,
    OrderFactory,
    PaymentFactory,
    ProductFactory,
    ProductVariantFactory,
    SeasonFactory,
    TicketCategoryFactory,
    TicketFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

OCTOBER = Period(date(2026, 10, 1), date(2026, 10, 31))


def at(year, month, day, hour=0, minute=0, second=0, microsecond=0):
    return timezone.make_aware(datetime(year, month, day, hour, minute, second, microsecond))


def booking_payment(amount, confirmed_at, **kwargs):
    return PaymentFactory(
        order=None, booking=BookingFactory(), amount=amount, confirmed_at=confirmed_at, **kwargs
    )


# --- Périodes ----------------------------------------------------------------------


def test_period_bounds_cover_whole_days():
    assert OCTOBER.start == at(2026, 10, 1)
    assert OCTOBER.end == at(2026, 11, 1)


def test_preset_periods():
    today = date(2026, 3, 15)

    assert indicators.this_month(today) == Period(date(2026, 3, 1), today)
    assert indicators.last_month(today) == Period(date(2026, 2, 1), date(2026, 2, 28))
    assert indicators.last_month(date(2026, 1, 10)) == Period(date(2025, 12, 1), date(2025, 12, 31))
    assert indicators.this_year(today) == Period(date(2026, 1, 1), today)
    assert indicators.last_twelve_months(today) == Period(date(2025, 4, 1), today)


def test_add_months_crosses_years():
    assert indicators.add_months(date(2026, 1, 31), -1) == date(2025, 12, 1)
    assert indicators.add_months(date(2026, 11, 5), 2) == date(2027, 1, 1)
    assert indicators.add_months(date(2026, 10, 24), -11) == date(2025, 11, 1)


def test_percent():
    assert indicators.percent(1, 3) == Decimal("33.3")
    assert indicators.percent(2, 3) == Decimal("66.7")
    assert indicators.percent(5, 0) is None


# --- Chiffre d'affaires ------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    ["INITIATED", "PENDING", "FAILED", "CANCELLED", "EXPIRED", "REFUNDED"],
)
def test_revenue_ignores_unconfirmed_payments(status):
    PaymentFactory(amount=Decimal("17000"), confirmed_at=at(2026, 10, 5))
    # Même avec une date de confirmation (paiement remboursé après coup, par exemple).
    PaymentFactory(status=status, amount=Decimal("50000"), confirmed_at=at(2026, 10, 6))

    assert indicators.revenue(OCTOBER).total == Decimal("17000")


def test_revenue_counts_payments_at_their_confirmation_date():
    PaymentFactory(amount=Decimal("1000"), confirmed_at=at(2026, 10, 1))  # première seconde
    PaymentFactory(amount=Decimal("2000"), confirmed_at=at(2026, 10, 31, 23, 59, 59, 999999))
    PaymentFactory(amount=Decimal("4000"), confirmed_at=at(2026, 9, 30, 23, 59, 59, 999999))
    PaymentFactory(amount=Decimal("8000"), confirmed_at=at(2026, 11, 1))

    assert indicators.revenue(OCTOBER).total == Decimal("3000")


def test_revenue_splits_shop_and_ticketing_and_counts_orders_once():
    order = OrderFactory()
    PaymentFactory(order=order, amount=Decimal("10000"), confirmed_at=at(2026, 10, 2))
    PaymentFactory(order=order, amount=Decimal("7000"), confirmed_at=at(2026, 10, 3))
    PaymentFactory(amount=Decimal("25000"), confirmed_at=at(2026, 10, 4))
    booking_payment(Decimal("5000"), at(2026, 10, 4))
    booking_payment(Decimal("15000"), at(2026, 10, 9))

    result = indicators.revenue(OCTOBER)

    assert result.shop == Decimal("42000")
    assert result.ticketing == Decimal("20000")
    assert result.total == Decimal("62000")
    assert result.payments == 5
    assert result.orders == 2
    assert result.average_order == Decimal("21000")


def test_average_order_rounds_to_the_franc_and_handles_no_order():
    for amount in ("10000", "10000", "10001"):
        PaymentFactory(amount=Decimal(amount), confirmed_at=at(2026, 10, 2))
    booking_payment(Decimal("5000"), at(2026, 10, 4))

    assert indicators.revenue(OCTOBER).average_order == Decimal("10000")
    assert indicators.revenue(Period(date(2026, 1, 1), date(2026, 1, 31))).average_order is None


def test_empty_period_gives_zero():
    result = indicators.revenue(OCTOBER)

    assert (result.total, result.shop, result.ticketing, result.payments) == (0, 0, 0, 0)


def test_revenue_by_month_lists_twelve_months_including_empty_ones():
    PaymentFactory(amount=Decimal("1000"), confirmed_at=at(2025, 11, 1))  # premier mois
    PaymentFactory(amount=Decimal("2000"), confirmed_at=at(2025, 11, 30, 23, 59))
    booking_payment(Decimal("500"), at(2026, 3, 15))
    PaymentFactory(amount=Decimal("3000"), confirmed_at=at(2026, 10, 24, 8))
    PaymentFactory(amount=Decimal("9999"), confirmed_at=at(2025, 10, 31, 23, 59))  # trop ancien
    PaymentFactory(status="FAILED", amount=Decimal("7777"), confirmed_at=at(2026, 3, 2))

    rows = indicators.revenue_by_month(date(2026, 10, 24))

    assert len(rows) == 12
    assert [row["month"] for row in rows][:2] == [date(2025, 11, 1), date(2025, 12, 1)]
    assert rows[-1]["month"] == date(2026, 10, 1)
    by_month = {row["month"]: (row["shop"], row["ticketing"], row["total"]) for row in rows}
    assert by_month[date(2025, 11, 1)] == (3000, 0, 3000)
    assert by_month[date(2026, 3, 1)] == (0, 500, 500)
    assert by_month[date(2026, 10, 1)] == (3000, 0, 3000)
    assert by_month[date(2026, 1, 1)] == (0, 0, 0)
    assert sum(row["total"] for row in rows) == Decimal("6500")


def test_revenue_by_method():
    PaymentFactory(method="CASH", amount=Decimal("2000"), confirmed_at=at(2026, 10, 2))
    PaymentFactory(method="CASH", amount=Decimal("3000"), confirmed_at=at(2026, 10, 3))
    PaymentFactory(
        method="MOBILE_MONEY_MANUAL", amount=Decimal("9000"), confirmed_at=at(2026, 10, 3)
    )
    PaymentFactory(
        method="BANK_TRANSFER", status="PENDING", amount=Decimal("50000"), confirmed_at=None
    )

    rows = indicators.revenue_by_method(OCTOBER)

    assert [(row["label"], row["amount"], row["count"]) for row in rows] == [
        ("Mobile Money (confirmé manuellement)", Decimal("9000"), 1),
        ("Espèces", Decimal("5000"), 2),
    ]


def test_pending_manual_payments():
    PaymentFactory(status="PENDING", amount=Decimal("17000"), confirmed_at=None)
    PaymentFactory(status="INITIATED", amount=Decimal("3000"), confirmed_at=None)
    PaymentFactory(status="PENDING", provider="SANDBOX", amount=Decimal("100"), confirmed_at=None)
    PaymentFactory(status="FAILED", amount=Decimal("200"), confirmed_at=None)
    PaymentFactory(amount=Decimal("300"))

    assert indicators.pending_manual_payments() == {"count": 2, "amount": Decimal("20000")}


def test_payments_in_lists_the_period_in_order():
    late = PaymentFactory(confirmed_at=at(2026, 10, 20))
    early = booking_payment(Decimal("5000"), at(2026, 10, 2))
    PaymentFactory(confirmed_at=at(2026, 9, 20))
    PaymentFactory(status="PENDING", confirmed_at=None)

    assert list(indicators.payments_in(OCTOBER)) == [early, late]


# --- Boutique ----------------------------------------------------------------------


def test_orders_overview_and_returns():
    for status, count in [
        ("PENDING_PAYMENT", 2),
        ("PAID", 3),
        ("PROCESSING", 1),
        ("SHIPPED", 4),
        ("DELIVERED", 5),
        ("CANCELLED", 6),
    ]:
        for _ in range(count):
            OrderFactory(status=status)
    order = Order.objects.first()
    for status in ["REQUESTED", "ACCEPTED", "RECEIVED", "REJECTED", "REFUNDED"]:
        ReturnRequest.objects.create(order=order, reason="Taille", status=status)

    assert indicators.orders_overview() == {"pending_payment": 2, "to_prepare": 4, "shipped": 4}
    assert indicators.open_returns_count() == 3


def test_low_stock_includes_the_threshold_itself():
    at_threshold = ProductVariantFactory(stock=3, low_stock_threshold=3)
    sold_out = ProductVariantFactory(stock=0, low_stock_threshold=3)
    ProductVariantFactory(stock=4, low_stock_threshold=3)
    ProductVariantFactory(stock=0, is_active=False)
    ProductVariantFactory(stock=0, product=ProductFactory(is_active=False))

    assert list(indicators.low_stock_variants()) == [sold_out, at_threshold]


def add_item(order, variant, quantity, unit_price=Decimal("15000")):
    return OrderItem.objects.create(
        order=order,
        variant=variant,
        product_name=variant.product.name,
        sku=variant.sku,
        unit_price=unit_price,
        quantity=quantity,
        line_total=unit_price * quantity,
    )


def test_best_sellers_only_count_paid_orders_of_the_period():
    jersey = ProductFactory(name="Maillot domicile")
    scarf = ProductFactory(name="Écharpe", base_price=Decimal("5000"))
    jersey_m = ProductVariantFactory(product=jersey, size="M")
    jersey_l = ProductVariantFactory(product=jersey, size="L")
    scarf_one = ProductVariantFactory(product=scarf, size="")
    paid = OrderFactory(status="DELIVERED", paid_at=at(2026, 10, 3))
    add_item(paid, jersey_m, 2)
    add_item(paid, jersey_l, 1)
    add_item(OrderFactory(status="PAID", paid_at=at(2026, 10, 20)), scarf_one, 5, Decimal("5000"))
    add_item(OrderFactory(status="CANCELLED", paid_at=at(2026, 10, 5)), jersey_m, 9)
    add_item(OrderFactory(status="PENDING_PAYMENT"), jersey_m, 9)
    add_item(OrderFactory(status="PAID", paid_at=at(2026, 9, 30)), jersey_m, 9)

    rows = indicators.best_sellers(OCTOBER)

    assert [(r["variant__product__name"], r["quantity"], r["amount"]) for r in rows] == [
        ("Écharpe", 5, Decimal("25000")),
        ("Maillot domicile", 3, Decimal("45000")),
    ]


# --- Billetterie -------------------------------------------------------------------


def test_ticket_sales_for_upcoming_matches():
    now = timezone.now()
    match = MatchFactory(kickoff_at=now + timedelta(days=3))
    honour = TicketCategoryFactory(match=match, capacity=50)
    stand = TicketCategoryFactory(match=match, capacity=150)
    confirmed = BookingFactory(match=match, status=Booking.Status.CONFIRMED)
    for category, status in [
        (honour, Ticket.Status.VALID),
        (stand, Ticket.Status.VALID),
        (stand, Ticket.Status.USED),
        (stand, Ticket.Status.CANCELLED),
    ]:
        TicketFactory(
            booking=confirmed,
            category=category,
            status=status,
            used_at=now if status == Ticket.Status.USED else None,
        )
    pending = BookingFactory(match=match, expires_at=now + timedelta(minutes=10))
    TicketFactory.create_batch(2, booking=pending, category=stand)
    expired = BookingFactory(match=match, expires_at=now - timedelta(minutes=1))
    TicketFactory(booking=expired, category=stand)
    cancelled = BookingFactory(match=match, status=Booking.Status.CANCELLED)
    TicketFactory(booking=cancelled, category=stand)
    PaymentFactory(order=None, booking=confirmed, amount=Decimal("20000"))
    PaymentFactory(order=None, booking=pending, status="PENDING", confirmed_at=None)
    # Ne figurent pas : match passé, match sans billets, match annulé.
    TicketCategoryFactory(
        match=MatchFactory(
            kickoff_at=now + timedelta(hours=3), status="FINISHED", home_score=0, away_score=0
        )
    )
    TicketCategoryFactory(match=MatchFactory(kickoff_at=now - timedelta(days=1)))
    MatchFactory(kickoff_at=now + timedelta(days=1))
    TicketCategoryFactory(
        match=MatchFactory(kickoff_at=now + timedelta(days=2), status="CANCELLED")
    )

    [sale] = indicators.ticket_sales(now)

    assert sale.match == match
    assert sale.capacity == 200
    assert sale.sold == 3
    assert sale.used == 1
    assert sale.reserved == 2
    assert sale.remaining == 195
    assert sale.fill_rate == Decimal("1.5")
    assert sale.revenue == Decimal("20000")


def test_ticket_sales_are_sorted_by_kickoff():
    now = timezone.now()
    later = TicketCategoryFactory(match=MatchFactory(kickoff_at=now + timedelta(days=9))).match
    sooner = TicketCategoryFactory(match=MatchFactory(kickoff_at=now + timedelta(days=2))).match

    assert [sale.match for sale in indicators.ticket_sales(now)] == [sooner, later]
    assert indicators.ticket_sales(now)[0].sold == 0
    assert indicators.ticket_sales(now)[0].revenue == 0


def test_pending_bookings_count_ignores_expired_holds():
    now = timezone.now()
    BookingFactory(expires_at=now + timedelta(minutes=5))
    BookingFactory(expires_at=now - timedelta(seconds=1))
    BookingFactory(status=Booking.Status.CONFIRMED)

    assert indicators.pending_bookings_count(now) == 1


# --- Sport -------------------------------------------------------------------------


def test_matches_awaiting_score(make_user):
    now = timezone.now()
    past = now - timedelta(hours=2)
    scheduled = MatchFactory(kickoff_at=past)
    live = MatchFactory(kickoff_at=past - timedelta(days=1), status="LIVE")
    MatchFactory(kickoff_at=past, status="FINISHED", home_score=1, away_score=0)
    MatchFactory(kickoff_at=past, status="POSTPONED")
    MatchFactory(kickoff_at=past, status="CANCELLED")
    MatchFactory(kickoff_at=now + timedelta(hours=1))

    director = make_user("sporting_director")

    assert list(indicators.matches_awaiting_score(director, now)) == [live, scheduled]


def test_coach_only_sees_matches_of_the_team_he_coaches(make_user):
    now = timezone.now()
    coach = make_user("coach")
    edition = CompetitionSeasonFactory()
    Staff.objects.create(
        first_name="Ali", last_name="Koné", role="HEAD_COACH", team=edition.team, user=coach
    )
    own = MatchFactory(competition_season=edition, kickoff_at=now - timedelta(hours=3))
    MatchFactory(kickoff_at=now - timedelta(hours=3))

    assert list(indicators.matches_awaiting_score(coach, now)) == [own]


def test_recently_finished_covers_two_weeks(make_user):
    now = timezone.now()
    finished = {"status": "FINISHED", "home_score": 2, "away_score": 2}
    recent = MatchFactory(kickoff_at=now - timedelta(days=13), **finished)
    MatchFactory(kickoff_at=now - timedelta(days=15), **finished)

    assert list(indicators.recently_finished(make_user("superadmin"), now)) == [recent]


def test_season_record_counts_our_results_home_and_away():
    season = SeasonFactory()
    ours = ClubFactory(name="Precis FC", is_own_club=True)
    edition = CompetitionSeasonFactory(season=season)
    rival, other = ClubFactory(), ClubFactory()
    finished = {"competition_season": edition, "status": "FINISHED"}
    MatchFactory(home_club=ours, away_club=rival, home_score=3, away_score=1, **finished)
    MatchFactory(home_club=rival, away_club=ours, home_score=0, away_score=2, **finished)
    MatchFactory(home_club=rival, away_club=ours, home_score=1, away_score=1, **finished)
    MatchFactory(home_club=ours, away_club=rival, home_score=0, away_score=4, **finished)
    # Exclus : match d'autres clubs, match non terminé, autre saison.
    MatchFactory(home_club=rival, away_club=other, home_score=5, away_score=0, **finished)
    MatchFactory(home_club=ours, away_club=rival, competition_season=edition)
    MatchFactory(home_club=ours, away_club=rival, status="FINISHED", home_score=9, away_score=0)

    record = indicators.season_record(season)

    assert (record.won, record.drawn, record.lost) == (2, 1, 1)
    assert (record.goals_for, record.goals_against) == (6, 6)
    assert record.played == 4
    assert record.goal_difference == 0
    assert indicators.season_record(None).played == 0
    assert Club.objects.filter(is_own_club=True).count() == 1


# --- Contenus, supporters, contact, académie ---------------------------------------


def test_article_counts(make_user):
    now = timezone.now()
    writer = make_user("writer")
    other = make_user("writer")
    Article.objects.create(title="A", status="IN_REVIEW", author=writer)
    Article.objects.create(title="B", status="DRAFT", author=writer)
    Article.objects.create(title="C", status="DRAFT", author=other)
    Article.objects.create(title="D", status="SCHEDULED", publish_at=now + timedelta(days=2))
    # Programmé dont l'heure est passée : déjà visible, donc compté comme publié.
    Article.objects.create(title="E", status="SCHEDULED", publish_at=now - timedelta(minutes=5))
    Article.objects.create(title="F", status="PUBLISHED", publish_at=now - timedelta(minutes=1))
    first_of_month = timezone.make_aware(
        datetime.combine(timezone.localdate(now).replace(day=1), datetime.min.time())
    )
    Article.objects.create(
        title="G", status="PUBLISHED", publish_at=first_of_month - timedelta(seconds=1)
    )
    Article.objects.create(title="H", status="ARCHIVED", publish_at=now - timedelta(minutes=1))

    counts = indicators.article_counts(writer)

    assert counts == {
        "in_review": 1,
        "scheduled": 1,
        "drafts": 2,
        "published_this_month": 2,
        "my_drafts": 1,
    }


def test_supporter_and_newsletter_counts():
    old = UserFactory()
    User.objects.filter(pk=old.pk).update(date_joined=at(2026, 9, 30, 23, 59))
    UserFactory()
    User.objects.filter(pk=UserFactory().pk).update(date_joined=at(2026, 10, 1))
    UserFactory(is_active=False)
    NewsletterSubscriber.objects.create(email="a@precisfc.test", is_confirmed=True)
    NewsletterSubscriber.objects.create(email="b@precisfc.test", is_confirmed=False)
    NewsletterSubscriber.objects.create(
        email="c@precisfc.test", is_confirmed=True, unsubscribed_at=timezone.now()
    )

    counts = indicators.supporter_counts(Period(date(2026, 10, 1), timezone.localdate()))

    assert counts["total"] == 3
    assert counts["new"] == 2
    assert indicators.newsletter_subscribers_count() == 1


def test_contact_counts():
    for status in ["NEW", "NEW", "IN_PROGRESS", "CLOSED", "SPAM"]:
        ContactMessage.objects.create(
            name="Awa", email="awa@precisfc.test", subject="Question", message="…", status=status
        )

    assert indicators.contact_counts() == {"new": 2, "in_progress": 1}


def test_application_counts_and_retention():
    today = date(2026, 10, 24)
    for status in ["SUBMITTED", "UNDER_REVIEW", "TRIAL_INVITED", "ACCEPTED", "REJECTED"]:
        ApplicationFactory(status=status)
    ApplicationFactory(status="REJECTED", retention_until=date(2026, 10, 23))
    ApplicationFactory(status="REJECTED", retention_until=today)  # pas encore dépassée

    counts = indicators.application_counts(today)

    assert counts == {"to_review": 2, "trial": 1, "open": 3, "retention_overdue": 1}
    assert Application.objects.count() == 7


# --- Affichage ---------------------------------------------------------------------

NBSP = chr(0xA0)


def test_home_page_shows_the_exact_figures(login):
    now = timezone.now()
    PaymentFactory(amount=Decimal("17000"), confirmed_at=now)
    booking_payment(Decimal("5000"), now)
    PaymentFactory(status="PENDING", amount=Decimal("8000"), confirmed_at=None)

    page = login("treasurer").get("/gestion/").content.decode()

    assert f"22{NBSP}000{NBSP}FCFA" in page  # chiffre d'affaires du mois
    assert f"17{NBSP}000{NBSP}FCFA" in page  # boutique, et panier moyen
    assert f"8{NBSP}000{NBSP}FCFA" in page  # paiement manuel à confirmer
    assert 'id="donnees-ca"' in page


def test_home_page_query_count_does_not_grow_with_data(login, django_assert_max_num_queries):
    client = login("superadmin")
    client.get("/gestion/")  # met en cache les paramètres du club

    def fill(count):
        now = timezone.now()
        for _ in range(count):
            PaymentFactory(confirmed_at=now)
            ProductVariantFactory(stock=0)
            match = MatchFactory(kickoff_at=now + timedelta(days=2))
            TicketFactory(category=TicketCategoryFactory(match=match))
            MatchFactory(kickoff_at=now - timedelta(hours=1))

    fill(2)
    with django_assert_max_num_queries(45) as small:
        client.get("/gestion/")
    fill(6)
    with django_assert_max_num_queries(45) as large:
        client.get("/gestion/")

    assert len(large.captured_queries) == len(small.captured_queries)


def test_payment_model_status_list_is_covered():
    """Un nouveau statut de paiement obligerait à revoir la règle du chiffre d'affaires."""
    assert set(Payment.Status.values) == {
        "INITIATED",
        "PENDING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
        "EXPIRED",
        "REFUNDED",
    }


def test_match_status_list_is_covered():
    assert set(Match.Status.values) == {"SCHEDULED", "LIVE", "FINISHED", "POSTPONED", "CANCELLED"}


# --- Vue d'ensemble (section 15 du cahier des charges) -----------------------------


def test_squad_and_match_counts():
    from tests.factories import PlayerFactory, TeamFactory

    team = TeamFactory()
    PlayerFactory.create_batch(3, team=team)
    TeamFactory()
    season = SeasonFactory()
    ours = ClubFactory(is_own_club=True)
    edition = CompetitionSeasonFactory(season=season, team=team)
    MatchFactory(
        competition_season=edition, home_club=ours, status="FINISHED", home_score=1, away_score=0
    )
    MatchFactory(competition_season=edition, away_club=ours)
    MatchFactory(competition_season=edition, away_club=ours, status="CANCELLED")
    MatchFactory(competition_season=edition)  # deux autres clubs
    MatchFactory(home_club=ours)  # autre saison

    assert indicators.squad_counts() == {"players": 3, "teams": 3}
    assert indicators.match_counts(season) == {"total": 2, "played": 1}
    assert indicators.match_counts(None) == {"total": 3, "played": 1}


def test_last_results_are_our_finished_matches_newest_first():
    ours = ClubFactory(is_own_club=True)
    now = timezone.now()
    finished = {"status": "FINISHED", "home_score": 1, "away_score": 0}
    older = MatchFactory(home_club=ours, kickoff_at=now - timedelta(days=9), **finished)
    newer = MatchFactory(away_club=ours, kickoff_at=now - timedelta(days=2), **finished)
    MatchFactory(kickoff_at=now - timedelta(days=1), **finished)  # sans nous
    MatchFactory(home_club=ours, kickoff_at=now - timedelta(days=1))  # pas joué

    assert list(indicators.last_results()) == [newer, older]


def test_published_articles_count():
    now = timezone.now()
    Article.objects.create(title="A", status="PUBLISHED", publish_at=now - timedelta(days=40))
    Article.objects.create(title="B", status="SCHEDULED", publish_at=now - timedelta(minutes=1))
    Article.objects.create(title="C", status="SCHEDULED", publish_at=now + timedelta(days=1))
    Article.objects.create(title="D", status="ARCHIVED", publish_at=now - timedelta(days=3))
    Article.objects.create(title="E", status="DRAFT")

    assert indicators.published_articles_count(now) == 2


def test_orders_and_tickets_sold_counts():
    month = indicators.this_month()
    old_order = OrderFactory()
    Order.objects.filter(pk=old_order.pk).update(created_at=month.start - timedelta(seconds=1))
    OrderFactory(status="CANCELLED")
    OrderFactory()
    confirmed = BookingFactory(status=Booking.Status.CONFIRMED)
    category = TicketCategoryFactory(match=confirmed.match)
    TicketFactory(booking=confirmed, category=category)
    TicketFactory(booking=confirmed, category=category, status="USED", used_at=timezone.now())
    TicketFactory(booking=confirmed, category=category, status="CANCELLED")
    TicketFactory(booking=BookingFactory(match=confirmed.match), category=category)  # en attente
    old_booking = BookingFactory(status=Booking.Status.CONFIRMED, match=confirmed.match)
    Booking.objects.filter(pk=old_booking.pk).update(created_at=month.start - timedelta(days=3))
    TicketFactory(booking=old_booking, category=category)

    assert indicators.orders_count(month) == {"total": 3, "this_period": 2}
    assert indicators.tickets_sold(month) == {"total": 3, "this_period": 2}


def test_out_of_stock_products():
    gone = ProductFactory(name="Écharpe")
    ProductVariantFactory(product=gone, stock=0, size="")
    ProductVariantFactory(product=gone, stock=5, size="XL", is_active=False)
    partial = ProductFactory(name="Maillot")
    ProductVariantFactory(product=partial, stock=0, size="M")
    ProductVariantFactory(product=partial, stock=2, size="L")
    hidden = ProductFactory(is_active=False)
    ProductVariantFactory(product=hidden, stock=0)
    ProductFactory(name="Sans variante")

    assert indicators.out_of_stock() == {"products": 1, "variants": 2}


def test_overview_matches_the_specification_list(login):
    """Les 11 indicateurs de la section 15, pour qui peut tout voir."""
    response = login("superadmin").get("/gestion/")

    labels = [item["label"] for item in response.context["overview"]]
    assert labels == [
        "Joueurs",
        "Équipes",
        "Matchs",
        "Articles publiés",
        "Commandes",
        "Chiffre d'affaires du mois",
        "Billets vendus",
        "Produits en rupture de stock",
        "Utilisateurs inscrits",
    ]
    page = response.content.decode()
    assert "Derniers résultats" in page
    assert "Prochains matchs" in page


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("writer", ["Joueurs", "Matchs", "Articles publiés"]),
        ("shop_manager", ["Commandes", "Produits en rupture de stock"]),
        ("treasurer", ["Commandes", "Chiffre d'affaires du mois", "Billets vendus"]),
        ("academy_manager", ["Joueurs", "Équipes"]),
        ("direction", 9),
    ],
)
def test_overview_follows_permissions(login, role, expected):
    labels = [item["label"] for item in login(role).get("/gestion/").context["overview"]]

    if isinstance(expected, int):
        assert len(labels) == expected
    else:
        assert labels == expected
