"""Indicateurs du tableau de bord, calculés directement en base.

Règle du chiffre d'affaires : seuls comptent les paiements **confirmés** (statut
« réussi »), à la date de leur confirmation. Un paiement initié, en attente, échoué,
annulé, expiré ou remboursé n'y figure jamais, quel que soit le statut de la commande.

Chaque fonction fait une seule requête (ou un nombre fixe), quel que soit le volume :
le tableau de bord reste rapide sur l'hébergement mutualisé.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, Exists, F, IntegerField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from apps.academy.models import Application
from apps.accounts.models import User
from apps.accounts.permissions import team_scope
from apps.competitions.models import Standing
from apps.contact.models import ContactMessage
from apps.matches.models import Match
from apps.media_library.models import Album, Photo, Video
from apps.news.models import Article
from apps.notifications.models import NewsletterSubscriber
from apps.orders.models import Order, OrderItem, ReturnRequest
from apps.payments.models import Payment
from apps.shop.models import Product, ProductVariant
from apps.teams.models import Player, Team
from apps.ticketing.models import Booking, Ticket, TicketCategory

ZERO = Decimal("0")

# --- Périodes ----------------------------------------------------------------------


@dataclass(frozen=True)
class Period:
    """Intervalle de dates [first, last], bornes comprises (jours du fuseau du club)."""

    first: date
    last: date

    @property
    def start(self) -> datetime:
        return start_of_day(self.first)

    @property
    def end(self) -> datetime:
        """Borne exclue : minuit le lendemain du dernier jour."""
        return start_of_day(self.last + timedelta(days=1))

    def contains(self, field: str) -> Q:
        return Q(**{f"{field}__gte": self.start, f"{field}__lt": self.end})


def start_of_day(day: date) -> datetime:
    return timezone.make_aware(datetime.combine(day, time.min))


def add_months(day: date, months: int) -> date:
    """Premier jour du mois situé ``months`` mois avant (négatif) ou après ``day``."""
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def this_month(today: date | None = None) -> Period:
    today = today or timezone.localdate()
    return Period(today.replace(day=1), today)


def last_month(today: date | None = None) -> Period:
    today = today or timezone.localdate()
    first = add_months(today, -1)
    return Period(first, today.replace(day=1) - timedelta(days=1))


def this_year(today: date | None = None) -> Period:
    today = today or timezone.localdate()
    return Period(date(today.year, 1, 1), today)


def last_twelve_months(today: date | None = None) -> Period:
    today = today or timezone.localdate()
    return Period(add_months(today, -11), today)


def percent(part, whole) -> Decimal | None:
    """Pourcentage arrondi au dixième, ``None`` si le total est nul."""
    if not whole:
        return None
    return (Decimal(part) * 100 / Decimal(whole)).quantize(Decimal("0.1"), ROUND_HALF_UP)


# --- Finances ----------------------------------------------------------------------


def confirmed_payments():
    return Payment.objects.filter(status=Payment.Status.SUCCEEDED)


@dataclass(frozen=True)
class Revenue:
    shop: Decimal
    ticketing: Decimal
    payments: int
    orders: int

    @property
    def total(self) -> Decimal:
        return self.shop + self.ticketing

    @property
    def average_order(self) -> Decimal | None:
        """Panier moyen : chiffre d'affaires boutique ÷ commandes payées sur la période."""
        if not self.orders:
            return None
        return (self.shop / self.orders).quantize(Decimal("1"), ROUND_HALF_UP)


def revenue(period: Period) -> Revenue:
    totals = (
        confirmed_payments()
        .filter(period.contains("confirmed_at"))
        .aggregate(
            shop=Sum("amount", filter=Q(order__isnull=False)),
            ticketing=Sum("amount", filter=Q(booking__isnull=False)),
            payments=Count("pk"),
            orders=Count("order", distinct=True),
        )
    )
    return Revenue(
        shop=totals["shop"] or ZERO,
        ticketing=totals["ticketing"] or ZERO,
        payments=totals["payments"],
        orders=totals["orders"],
    )


def revenue_by_month(today: date | None = None, months: int = 12) -> list[dict]:
    """Chiffre d'affaires mois par mois (mois sans paiement compris), du plus ancien au
    mois en cours."""
    today = today or timezone.localdate()
    first = add_months(today, -(months - 1))
    period = Period(first, today)
    rows = (
        confirmed_payments()
        .filter(period.contains("confirmed_at"))
        .annotate(month=TruncMonth("confirmed_at"))
        .values("month")
        .annotate(
            shop=Sum("amount", filter=Q(order__isnull=False)),
            ticketing=Sum("amount", filter=Q(booking__isnull=False)),
        )
        .order_by("month")
    )
    by_month = {}
    for row in rows:
        month = row["month"]
        if isinstance(month, datetime):
            month = timezone.localtime(month).date() if timezone.is_aware(month) else month.date()
        by_month[month.replace(day=1)] = row
    result = []
    for offset in range(months):
        month = add_months(first, offset)
        row = by_month.get(month, {})
        shop, ticketing = row.get("shop") or ZERO, row.get("ticketing") or ZERO
        result.append(
            {"month": month, "shop": shop, "ticketing": ticketing, "total": shop + ticketing}
        )
    return result


def revenue_by_method(period: Period) -> list[dict]:
    labels = dict(Payment.Method.choices)
    rows = (
        confirmed_payments()
        .filter(period.contains("confirmed_at"))
        .values("method")
        .annotate(amount=Sum("amount"), count=Count("pk"))
        .order_by("-amount", "method")
    )
    return [
        {"method": row["method"], "label": labels.get(row["method"], row["method"]), **row}
        for row in rows
    ]


def payments_in(period: Period):
    """Paiements confirmés de la période, pour le détail et l'export."""
    return (
        confirmed_payments()
        .filter(period.contains("confirmed_at"))
        .select_related("order", "booking__match__home_club", "booking__match__away_club")
        .select_related("confirmed_by")
        .order_by("confirmed_at", "pk")
    )


AWAITING_PAYMENT = (Payment.Status.INITIATED, Payment.Status.PENDING)


def pending_manual_payments() -> dict:
    """Paiements manuels (espèces, Mobile Money…) qu'une personne habilitée doit confirmer."""
    totals = Payment.objects.filter(
        provider=Payment.Provider.MANUAL, status__in=AWAITING_PAYMENT
    ).aggregate(count=Count("pk"), amount=Sum("amount"))
    return {"count": totals["count"], "amount": totals["amount"] or ZERO}


# --- Boutique ----------------------------------------------------------------------

PAID_ORDER_STATUSES = (
    Order.Status.PAID,
    Order.Status.PROCESSING,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
)
TO_PREPARE = (Order.Status.PAID, Order.Status.PROCESSING)
OPEN_RETURNS = (
    ReturnRequest.Status.REQUESTED,
    ReturnRequest.Status.ACCEPTED,
    ReturnRequest.Status.RECEIVED,
)


def orders_overview() -> dict:
    return Order.objects.aggregate(
        pending_payment=Count("pk", filter=Q(status=Order.Status.PENDING_PAYMENT)),
        to_prepare=Count("pk", filter=Q(status__in=TO_PREPARE)),
        shipped=Count("pk", filter=Q(status=Order.Status.SHIPPED)),
    )


def open_returns_count() -> int:
    return ReturnRequest.objects.filter(status__in=OPEN_RETURNS).count()


def low_stock_variants():
    """Variantes en vente dont le stock a atteint le seuil d'alerte (seuil compris)."""
    return (
        ProductVariant.objects.filter(
            is_active=True, product__is_active=True, stock__lte=F("low_stock_threshold")
        )
        .select_related("product")
        .order_by("stock", "product__name", "size", "color")
    )


def best_sellers(period: Period, limit: int = 5) -> list[dict]:
    """Produits les plus vendus : commandes payées sur la période, annulées exclues."""
    return list(
        OrderItem.objects.filter(order__status__in=PAID_ORDER_STATUSES)
        .filter(period.contains("order__paid_at"))
        .values("variant__product_id", "variant__product__name")
        .annotate(quantity=Sum("quantity"), amount=Sum("line_total"))
        .order_by("-quantity", "-amount", "variant__product__name")[:limit]
    )


# --- Billetterie -------------------------------------------------------------------


@dataclass(frozen=True)
class TicketSales:
    match: Match
    capacity: int
    sold: int
    reserved: int
    used: int
    revenue: Decimal

    @property
    def fill_rate(self) -> Decimal | None:
        return percent(self.sold, self.capacity)

    @property
    def remaining(self) -> int:
        return max(self.capacity - self.sold - self.reserved, 0)


def _count_tickets(**filters):
    return Coalesce(
        Subquery(
            Ticket.objects.filter(category__match=OuterRef("pk"), **filters)
            .values("category__match")
            .annotate(total=Count("pk"))
            .values("total"),
            output_field=IntegerField(),
        ),
        0,
    )


def ticket_sales(now: datetime | None = None, limit: int = 5) -> list[TicketSales]:
    """Matchs à venir mis en vente : places, billets vendus (réservations confirmées),
    places bloquées par des réservations en attente encore valides, entrées contrôlées,
    recette confirmée."""
    now = now or timezone.now()
    capacity = Subquery(
        TicketCategory.objects.filter(match=OuterRef("pk"))
        .values("match")
        .annotate(total=Sum("capacity"))
        .values("total"),
        output_field=IntegerField(),
    )
    match_revenue = Subquery(
        confirmed_payments()
        .filter(booking__match=OuterRef("pk"))
        .values("booking__match")
        .annotate(total=Sum("amount"))
        .values("total")
    )
    confirmed = Booking.Status.CONFIRMED
    matches = (
        Match.objects.filter(kickoff_at__gte=now, ticket_categories__isnull=False)
        .exclude(status__in=[Match.Status.CANCELLED, Match.Status.FINISHED])
        .distinct()
        .select_related("home_club", "away_club")
        .annotate(
            capacity_total=capacity,
            sold_total=_count_tickets(booking__status=confirmed, status__in=["VALID", "USED"]),
            reserved_total=_count_tickets(
                booking__status=Booking.Status.PENDING, booking__expires_at__gt=now
            ),
            used_total=_count_tickets(booking__status=confirmed, status="USED"),
            revenue_total=match_revenue,
        )
        .order_by("kickoff_at")[:limit]
    )
    return [
        TicketSales(
            match=match,
            capacity=match.capacity_total or 0,
            sold=match.sold_total,
            reserved=match.reserved_total,
            used=match.used_total,
            revenue=match.revenue_total or ZERO,
        )
        for match in matches
    ]


def pending_bookings_count(now: datetime | None = None) -> int:
    now = now or timezone.now()
    return Booking.objects.filter(status=Booking.Status.PENDING, expires_at__gt=now).count()


# --- Sport -------------------------------------------------------------------------

TO_SCORE = (Match.Status.SCHEDULED, Match.Status.LIVE)


def scoped_matches(user):
    """Matchs que l'utilisateur peut saisir : tous, ou ceux des équipes qu'il entraîne."""
    scope = team_scope(user)
    matches = Match.objects.select_related(
        "home_club", "away_club", "competition_season__competition", "competition_season__team"
    )
    if scope is not None:
        matches = matches.filter(competition_season__team_id__in=scope)
    return matches


def matches_awaiting_score(user, now: datetime | None = None):
    """Matchs dont le coup d'envoi est passé mais qui ne sont pas encore terminés."""
    now = now or timezone.now()
    return (
        scoped_matches(user)
        .filter(kickoff_at__lte=now, status__in=TO_SCORE)
        .order_by("kickoff_at", "pk")
    )


def recently_finished(user, now: datetime | None = None, days: int = 14):
    """Matchs terminés récemment : un score saisi par erreur se corrige ici."""
    now = now or timezone.now()
    return (
        scoped_matches(user)
        .filter(
            status=Match.Status.FINISHED,
            kickoff_at__lte=now,
            kickoff_at__gte=now - timedelta(days=days),
        )
        .order_by("-kickoff_at", "-pk")
    )


def upcoming_own_matches(now: datetime | None = None, limit: int = 5):
    now = now or timezone.now()
    return (
        Match.objects.own_club()
        .filter(kickoff_at__gte=now, status__in=TO_SCORE)
        .select_related("home_club", "away_club", "competition_season__competition")
        .order_by("kickoff_at")[:limit]
    )


@dataclass(frozen=True)
class Record:
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0

    @property
    def played(self) -> int:
        return self.won + self.drawn + self.lost

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against


def season_record(season) -> Record:
    """Bilan de notre club sur la saison : matchs terminés, toutes compétitions."""
    if season is None:
        return Record()
    won = drawn = lost = goals_for = goals_against = 0
    rows = (
        Match.objects.own_club()
        .filter(competition_season__season=season, status=Match.Status.FINISHED)
        .values_list("home_club__is_own_club", "home_score", "away_score")
    )
    for at_home, home_score, away_score in rows:
        ours, theirs = (home_score, away_score) if at_home else (away_score, home_score)
        goals_for += ours
        goals_against += theirs
        if ours > theirs:
            won += 1
        elif ours == theirs:
            drawn += 1
        else:
            lost += 1
    return Record(won, drawn, lost, goals_for, goals_against)


def own_standings(season):
    """Rang de notre club dans chaque classement de la saison."""
    if season is None:
        return Standing.objects.none()
    return (
        Standing.objects.filter(competition_season__season=season, club__is_own_club=True)
        .select_related("competition_season__competition", "competition_season__team")
        .order_by("competition_season__team__order", "competition_season__competition__name")
    )


# --- Contenus ----------------------------------------------------------------------


def article_counts(user=None, today: date | None = None) -> dict:
    now = timezone.now()
    month = this_month(today)
    status = Article.Status
    counts = Article.objects.aggregate(
        in_review=Count("pk", filter=Q(status=status.IN_REVIEW)),
        scheduled=Count("pk", filter=Q(status=status.SCHEDULED, publish_at__gt=now)),
        drafts=Count("pk", filter=Q(status=status.DRAFT)),
        published_this_month=Count(
            "pk",
            filter=Q(status__in=[status.PUBLISHED, status.SCHEDULED], publish_at__lte=now)
            & month.contains("publish_at"),
        ),
        my_drafts=Count("pk", filter=Q(status=status.DRAFT, author_id=getattr(user, "pk", None))),
    )
    return counts


def media_counts() -> dict:
    return {
        "albums": Album.objects.filter(is_published=True).count(),
        "photos": Photo.objects.count(),
        "videos": Video.objects.filter(is_published=True).count(),
    }


# --- Supporters, contact, académie --------------------------------------------------


def supporter_counts(period: Period) -> dict:
    return User.objects.filter(is_active=True).aggregate(
        total=Count("pk"), new=Count("pk", filter=period.contains("date_joined"))
    )


def newsletter_subscribers_count() -> int:
    return NewsletterSubscriber.objects.filter(
        is_confirmed=True, unsubscribed_at__isnull=True
    ).count()


def contact_counts() -> dict:
    status = ContactMessage.Status
    return ContactMessage.objects.aggregate(
        new=Count("pk", filter=Q(status=status.NEW)),
        in_progress=Count("pk", filter=Q(status=status.IN_PROGRESS)),
    )


OPEN_APPLICATIONS = (
    Application.Status.SUBMITTED,
    Application.Status.UNDER_REVIEW,
    Application.Status.TRIAL_INVITED,
)


def application_counts(today: date | None = None) -> dict:
    today = today or timezone.localdate()
    status = Application.Status
    return Application.objects.aggregate(
        to_review=Count("pk", filter=Q(status__in=[status.SUBMITTED, status.UNDER_REVIEW])),
        trial=Count("pk", filter=Q(status=status.TRIAL_INVITED)),
        open=Count("pk", filter=Q(status__in=OPEN_APPLICATIONS)),
        retention_overdue=Count("pk", filter=Q(retention_until__lt=today)),
    )


# --- Vue d'ensemble (indicateurs de la section 15 du cahier des charges) ------------

SOLD_TICKET_STATUSES = (Ticket.Status.VALID, Ticket.Status.USED)


def squad_counts() -> dict:
    return {"players": Player.objects.count(), "teams": Team.objects.count()}


def match_counts(season) -> dict:
    """Matchs de notre club sur la saison (toutes saisons s'il n'y en a pas en cours)."""
    matches = Match.objects.own_club().exclude(status=Match.Status.CANCELLED)
    if season is not None:
        matches = matches.filter(competition_season__season=season)
    return matches.aggregate(
        total=Count("pk"), played=Count("pk", filter=Q(status=Match.Status.FINISHED))
    )


def last_results(limit: int = 5):
    return (
        Match.objects.own_club()
        .filter(status=Match.Status.FINISHED)
        .select_related("home_club", "away_club", "competition_season__competition")
        .order_by("-kickoff_at", "-pk")[:limit]
    )


def published_articles_count(now: datetime | None = None) -> int:
    return Article.objects.published(now).count()


def orders_count(period: Period) -> dict:
    return Order.objects.aggregate(
        total=Count("pk"), this_period=Count("pk", filter=period.contains("created_at"))
    )


def tickets_sold(period: Period) -> dict:
    """Billets vendus : billets valides ou utilisés des réservations confirmées."""
    return Ticket.objects.filter(
        booking__status=Booking.Status.CONFIRMED, status__in=SOLD_TICKET_STATUSES
    ).aggregate(
        total=Count("pk"), this_period=Count("pk", filter=period.contains("booking__created_at"))
    )


def out_of_stock() -> dict:
    """Produits en vente dont plus aucune variante n'est disponible, et variantes
    épuisées (une taille peut manquer alors que le produit reste en vente)."""
    in_stock = ProductVariant.objects.filter(product=OuterRef("pk"), is_active=True, stock__gt=0)
    on_sale = ProductVariant.objects.filter(product=OuterRef("pk"), is_active=True)
    products = (
        Product.objects.filter(is_active=True)
        .filter(Exists(on_sale))
        .exclude(Exists(in_stock))
        .count()
    )
    variants = ProductVariant.objects.filter(
        is_active=True, product__is_active=True, stock=0
    ).count()
    return {"products": products, "variants": variants}
