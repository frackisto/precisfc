"""Fabriques de données de test partagées par toutes les applications."""

from datetime import date, timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from apps.academy.models import Application
from apps.accounts.models import User
from apps.competitions.models import Club, Competition, CompetitionSeason, Season
from apps.matches.models import Match
from apps.orders.models import Order, ShippingMethod
from apps.payments.models import Payment
from apps.shop.models import Product, ProductCategory, ProductVariant
from apps.teams.models import Player, Team
from apps.ticketing.models import Booking, Ticket, TicketCategory


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"supporter{n}@precisfc.test")
    # Haché avant l'enregistrement : la session ouverte par force_login() reste valide.
    password = factory.django.Password("Mot-de-passe-test-2026")


class SeasonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Season

    name = factory.Sequence(lambda n: f"{2000 + n}-{2001 + n}")
    start_date = factory.Sequence(lambda n: date(2000 + n, 8, 1))
    end_date = factory.LazyAttribute(lambda obj: obj.start_date + timedelta(days=300))


class ClubFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Club

    name = factory.Sequence(lambda n: f"Club adverse {n}")


class CompetitionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Competition

    name = factory.Sequence(lambda n: f"Ligue {n}")
    kind = Competition.Kind.LEAGUE


class TeamFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Team

    name = factory.Sequence(lambda n: f"Équipe {n}")
    category = Team.Category.FIRST


class PlayerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Player

    team = factory.SubFactory(TeamFactory)
    first_name = "Yao"
    last_name = factory.Sequence(lambda n: f"Kouassi {n}")
    position = Player.Position.MF
    birth_date = date(1998, 5, 17)


class CompetitionSeasonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CompetitionSeason

    competition = factory.SubFactory(CompetitionFactory)
    season = factory.SubFactory(SeasonFactory)
    team = factory.SubFactory(TeamFactory)


class MatchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Match

    competition_season = factory.SubFactory(CompetitionSeasonFactory)
    home_club = factory.SubFactory(ClubFactory)
    away_club = factory.SubFactory(ClubFactory)
    kickoff_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))


class ProductCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductCategory

    name = factory.Sequence(lambda n: f"Maillots {n}")


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    category = factory.SubFactory(ProductCategoryFactory)
    name = factory.Sequence(lambda n: f"Maillot domicile {n}")
    base_price = Decimal("15000")


class ProductVariantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductVariant

    product = factory.SubFactory(ProductFactory)
    sku = factory.Sequence(lambda n: f"MAI-DOM-{n:04d}")
    size = "M"
    stock = 10


class ShippingMethodFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ShippingMethod

    name = "Livraison Abidjan"
    zone_label = "Abidjan"
    fee = Decimal("2000")


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    number = factory.Sequence(lambda n: f"CMD-{n:06d}")
    email = "client@precisfc.test"
    phone = "+2250701020304"
    shipping_full_name = "Awa Traoré"
    shipping_method = factory.SubFactory(ShippingMethodFactory)
    subtotal = Decimal("15000")
    discount = Decimal("0")
    shipping_fee = Decimal("2000")
    total = Decimal("17000")


class BookingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Booking

    reference = factory.Sequence(lambda n: f"RES-{n:06d}")
    user = factory.SubFactory(UserFactory)
    match = factory.SubFactory(MatchFactory)
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=15))
    total = Decimal("5000")


class ApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Application

    reference = factory.Sequence(lambda n: f"CAND-{n:05d}")
    first_name = "Moussa"
    last_name = "Diabaté"
    birth_date = date(2000, 3, 9)
    gender = Application.Gender.MALE
    city = "Abidjan"
    consent_given = True
    consent_at = factory.LazyFunction(timezone.now)


class TicketCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TicketCategory

    match = factory.SubFactory(MatchFactory)
    name = factory.Sequence(lambda n: f"Tribune {n}")
    price = Decimal("5000")
    capacity = 100


class TicketFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Ticket

    category = factory.SubFactory(TicketCategoryFactory)
    booking = factory.SubFactory(BookingFactory, match=factory.SelfAttribute("..category.match"))
    holder_name = "Awa Traoré"


class PaymentFactory(factory.django.DjangoModelFactory):
    """Paiement confirmé d'une commande (par défaut) ; ``booking=…`` pour la billetterie."""

    class Meta:
        model = Payment

    order = factory.SubFactory(OrderFactory)
    provider = Payment.Provider.MANUAL
    method = Payment.Method.CASH
    amount = Decimal("17000")
    status = Payment.Status.SUCCEEDED
    confirmed_at = factory.LazyFunction(timezone.now)
