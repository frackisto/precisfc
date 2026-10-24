"""Données de démonstration du tableau de bord : ventes, paiements, billets, messages…

    python manage.py demo_dashboard           # crée (ou recrée) la démonstration
    python manage.py demo_dashboard --delete  # la supprime

Contenu :
- boutique : 4 produits (dont une écharpe en rupture et une taille en stock bas) et
  12 mois de commandes payées, plus des commandes à préparer, en attente de paiement,
  expédiées, annulées et remboursées (seuls les paiements confirmés comptent) ;
- paiements manuels en attente de confirmation ;
- billetterie sur les matchs de la saison de démonstration (``demo_season``) s'ils
  existent : billets vendus, réservations en attente, recette ;
- messages de contact, candidatures (dont une à supprimer), abonnés à la newsletter ;
- quatre comptes pour essayer le tableau de bord par rôle (mot de passe affiché).

Tout ce qui est créé est repérable (« DEMO- », slug « demo-gestion- », adresses
« @gestion.demo.precisfc.test ») : la suppression ne touche rien d'autre.
"""

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.academy.models import Application
from apps.accounts import roles
from apps.accounts.models import User
from apps.accounts.roles import assign_role
from apps.contact.models import ContactMessage
from apps.dashboard.indicators import add_months
from apps.matches.models import Match
from apps.news.management.commands.demo_news import DEMO_PASSWORD
from apps.notifications.models import NewsletterSubscriber
from apps.orders.models import Order, OrderItem, ReturnRequest, ShippingMethod
from apps.payments.models import Payment
from apps.shop.models import Product, ProductCategory, ProductVariant
from apps.ticketing.models import Booking, Ticket, TicketCategory

REF = "DEMO-"
SLUG = "demo-gestion-"
DEMO_DOMAIN = "gestion.demo.precisfc.test"
ACCOUNTS = [
    (f"direction@{DEMO_DOMAIN}", roles.DIRECTION, "Direction (démo)"),
    (f"tresorier@{DEMO_DOMAIN}", roles.TREASURER, "Trésorier (démo)"),
    (f"boutique@{DEMO_DOMAIN}", roles.SHOP_MANAGER, "Boutique (démo)"),
    (f"sportif@{DEMO_DOMAIN}", roles.SPORTING_DIRECTOR, "Sportif (démo)"),
]
SUPPORTER = f"supporter@{DEMO_DOMAIN}"

# (nom, prix, [(taille, stock)])
PRODUCTS = [
    ("Maillot domicile (démo)", "15000", [("S", 12), ("M", 2), ("L", 9), ("XL", 6)]),
    ("Maillot extérieur (démo)", "15000", [("M", 8), ("L", 7)]),
    ("Écharpe du club (démo)", "5000", [("", 0)]),
    ("Casquette (démo)", "7000", [("", 15)]),
]
METHODS = [Payment.Method.CASH, Payment.Method.MOBILE_MONEY_MANUAL, Payment.Method.BANK_TRANSFER]


def aware(day: date, hour: int = 12) -> datetime:
    return timezone.make_aware(datetime.combine(day, time(hour)))


class Command(BaseCommand):
    help = "Crée (ou supprime avec --delete) les données de démonstration du tableau de bord."

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true", help="Supprime la démonstration.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Autorise l'exécution hors développement (comptes au mot de passe connu !).",
        )

    def handle(self, *args, delete=False, force=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError(
                "Commande de démonstration : réservée au développement (DEBUG). "
                "Ajouter --force pour l'exécuter quand même."
            )
        self.delete_demo()
        if delete:
            self.stdout.write(self.style.SUCCESS("Démonstration du tableau de bord supprimée."))
            return
        summary = self.create_demo()
        accounts = "\n".join(f"  - {email} ({roles.ROLES[key].name})" for email, key, _ in ACCOUNTS)
        self.stdout.write(
            self.style.SUCCESS(
                f"Tableau de bord de démonstration prêt : {summary}. Voir /gestion/.\n"
                f"Comptes (mot de passe {DEMO_PASSWORD}) :\n{accounts}"
            )
        )
        if "billetterie" not in summary:
            self.stdout.write(
                self.style.WARNING(
                    "Billetterie non créée : lancez d'abord « python manage.py demo_season »."
                )
            )

    # --- Suppression ---------------------------------------------------------------

    @transaction.atomic
    def delete_demo(self):
        orders = Order.objects.filter(number__startswith=REF)
        bookings = Booking.objects.filter(reference__startswith=REF)
        Payment.objects.filter(order__in=orders).delete()
        Payment.objects.filter(booking__in=bookings).delete()
        ReturnRequest.objects.filter(order__in=orders).delete()
        orders.delete()
        bookings.delete()
        TicketCategory.objects.filter(name__endswith="(démo gestion)").delete()
        ProductVariant.objects.filter(product__slug__startswith=SLUG).delete()
        Product.objects.filter(slug__startswith=SLUG).delete()
        ProductCategory.objects.filter(slug__startswith=SLUG).delete()
        ShippingMethod.objects.filter(name__endswith="(démo gestion)").delete()
        ContactMessage.objects.filter(email__endswith=f"@{DEMO_DOMAIN}").delete()
        Application.objects.filter(reference__startswith=REF).delete()
        NewsletterSubscriber.objects.filter(email__endswith=f"@{DEMO_DOMAIN}").delete()
        User.objects.filter(email__endswith=f"@{DEMO_DOMAIN}").delete()

    # --- Création --------------------------------------------------------------------

    def account(self, email, first_name, role=None):
        user = User.objects.create_user(email, password=DEMO_PASSWORD, first_name=first_name)
        if role:
            assign_role(user, role)
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
        return user

    @transaction.atomic
    def create_demo(self) -> str:
        rng = random.Random(2026)  # noqa: S311  (données fictives reproductibles)
        today = timezone.localdate()
        users = {key: self.account(email, name, key) for email, key, name in ACCOUNTS}
        self.treasurer = users[roles.TREASURER]
        self.supporter = self.account(SUPPORTER, "Supporter (démo)")
        variants = self.create_catalogue()
        orders = self.create_orders(rng, today, variants)
        tickets = self.create_ticketing(rng, today)
        self.create_relations(today)
        parts = [f"{orders} commandes"]
        if tickets:
            parts.append(f"{tickets} billets en billetterie")
        return ", ".join(parts)

    def create_catalogue(self):
        category = ProductCategory.objects.create(name="Boutique (démo)", slug=f"{SLUG}boutique")
        variants = []
        for index, (name, price, sizes) in enumerate(PRODUCTS):
            product = Product.objects.create(
                category=category, name=name, slug=f"{SLUG}{index}", base_price=Decimal(price)
            )
            for size, stock in sizes:
                variants.append(
                    ProductVariant.objects.create(
                        product=product,
                        sku=f"DEMO-{index}-{size or 'U'}",
                        size=size,
                        stock=stock,
                    )
                )
        self.shipping = ShippingMethod.objects.create(
            name="Livraison Abidjan (démo gestion)", zone_label="Abidjan", fee=Decimal("2000")
        )
        return variants

    def create_order(self, rng, number, variants, status, created, payment_status=None):
        # Jamais dans le futur (le 1er du mois, par exemple).
        created = min(created, timezone.now() - timedelta(hours=3))
        lines = rng.sample(variants, rng.randint(1, 2))
        quantities = [rng.randint(1, 3) for _ in lines]
        subtotal = sum(
            (line.product.base_price * qty for line, qty in zip(lines, quantities, strict=True)),
            Decimal("0"),
        )
        paid = payment_status == Payment.Status.SUCCEEDED
        order = Order.objects.create(
            number=f"{REF}{number:05d}",
            email=SUPPORTER,
            phone="+2250701020304",
            shipping_full_name="Supporter de démonstration",
            shipping_method=self.shipping,
            status=status,
            subtotal=subtotal,
            shipping_fee=self.shipping.fee,
            total=subtotal + self.shipping.fee,
            paid_at=created + timedelta(hours=2) if paid or status == "REFUNDED" else None,
        )
        Order.objects.filter(pk=order.pk).update(created_at=created)
        for line, qty in zip(lines, quantities, strict=True):
            OrderItem.objects.create(
                order=order,
                variant=line,
                product_name=line.product.name,
                sku=line.sku,
                size=line.size,
                unit_price=line.product.base_price,
                quantity=qty,
                line_total=line.product.base_price * qty,
            )
        if payment_status:
            confirmed = payment_status in (Payment.Status.SUCCEEDED, Payment.Status.REFUNDED)
            Payment.objects.create(
                order=order,
                provider=Payment.Provider.MANUAL,
                method=rng.choice(METHODS),
                amount=order.total,
                status=payment_status,
                confirmed_at=created + timedelta(hours=2) if confirmed else None,
                confirmed_by=self.treasurer if confirmed else None,
            )
        return order

    def create_orders(self, rng, today, variants) -> int:
        number = 0
        # Historique : 12 mois de commandes livrées (la saison monte en puissance).
        for months_ago in range(11, -1, -1):
            first = add_months(today, -months_ago)
            last_day = today.day if months_ago == 0 else 28
            for _ in range(rng.randint(2, 4) + (11 - months_ago) // 3):
                number += 1
                day = first.replace(day=rng.randint(1, max(last_day - 1, 1)))
                self.create_order(
                    rng, number, variants, "DELIVERED", aware(day, rng.randint(9, 19)), "SUCCEEDED"
                )
        recent = aware(today, 8) - timedelta(days=1)
        for status, payment in [
            ("PAID", "SUCCEEDED"),
            ("PAID", "SUCCEEDED"),
            ("PROCESSING", "SUCCEEDED"),
            ("SHIPPED", "SUCCEEDED"),
            ("PENDING_PAYMENT", "PENDING"),  # espèces annoncées, à confirmer
            ("PENDING_PAYMENT", "PENDING"),
            ("PENDING_PAYMENT", "INITIATED"),
            ("CANCELLED", "FAILED"),
            ("REFUNDED", "REFUNDED"),  # remboursée : hors chiffre d'affaires
        ]:
            number += 1
            order = self.create_order(rng, number, variants, status, recent, payment)
        ReturnRequest.objects.create(order=order, reason="Taille trop petite (démo).")
        return number

    def create_ticketing(self, rng, today) -> int:
        matches = Match.objects.filter(
            competition_season__season__slug__startswith="demo-", home_club__is_own_club=True
        ).order_by("kickoff_at")
        now = timezone.now()
        past = list(matches.filter(status="FINISHED"))[-3:]
        upcoming = list(matches.filter(kickoff_at__gte=now).exclude(status="FINISHED"))[:2]
        sold = 0
        reference = 0
        for match in past + upcoming:
            is_past = match.status == Match.Status.FINISHED
            categories = [
                TicketCategory.objects.create(
                    match=match,
                    name=f"{name} (démo gestion)",
                    price=Decimal(price),
                    capacity=capacity,
                )
                for name, price, capacity in [
                    ("Tribune d'honneur", "10000", 60),
                    ("Tribune couverte", "5000", 200),
                    ("Pourtour", "2000", 400),
                ]
            ]
            for category in categories:
                rate = rng.uniform(0.55, 0.9) if is_past else rng.uniform(0.15, 0.45)
                to_sell = int(category.capacity * rate)
                while to_sell > 0:
                    reference += 1
                    count = min(rng.randint(1, 4), to_sell)
                    to_sell -= count
                    sold += count
                    booked = min(match.kickoff_at, now) - timedelta(days=rng.randint(1, 6))
                    booking = Booking.objects.create(
                        reference=f"{REF}R{reference:05d}",
                        user=self.supporter,
                        match=match,
                        status=Booking.Status.CONFIRMED,
                        total=category.price * count,
                    )
                    Ticket.objects.bulk_create(
                        Ticket(
                            booking=booking,
                            category=category,
                            holder_name="Supporter de démonstration",
                            status="USED" if is_past else "VALID",
                            used_at=min(match.kickoff_at, now) if is_past else None,
                        )
                        for _ in range(count)
                    )
                    Payment.objects.create(
                        booking=booking,
                        provider=Payment.Provider.MANUAL,
                        method=rng.choice(METHODS[:2]),
                        amount=booking.total,
                        status=Payment.Status.SUCCEEDED,
                        confirmed_at=booked,
                        confirmed_by=self.treasurer,
                    )
            if not is_past:
                # Réservations en attente : places bloquées jusqu'à leur échéance.
                for _ in range(3):
                    reference += 1
                    booking = Booking.objects.create(
                        reference=f"{REF}R{reference:05d}",
                        user=self.supporter,
                        match=match,
                        expires_at=now + timedelta(minutes=15),
                        total=categories[1].price * 2,
                    )
                    Ticket.objects.bulk_create(
                        Ticket(booking=booking, category=categories[1], holder_name="Démo")
                        for _ in range(2)
                    )
        return sold

    def create_relations(self, today):
        for number, (status, subject) in enumerate(
            [
                ("NEW", "Demande de partenariat (démo)"),
                ("NEW", "Question sur la billetterie (démo)"),
                ("IN_PROGRESS", "Recrutement d'un jeune joueur (démo)"),
                ("CLOSED", "Remerciements (démo)"),
            ]
        ):
            ContactMessage.objects.create(
                name="Contact démo",
                email=f"contact{number}@{DEMO_DOMAIN}",
                subject=subject,
                message="Message de démonstration.",
                status=status,
            )
        now = timezone.now()
        for number, (status, retention) in enumerate(
            [
                ("SUBMITTED", None),
                ("SUBMITTED", None),
                ("UNDER_REVIEW", None),
                ("TRIAL_INVITED", None),
                ("REJECTED", today - timedelta(days=3)),  # durée de conservation dépassée
            ]
        ):
            Application.objects.create(
                reference=f"{REF}C{number:04d}",
                first_name="Candidat",
                last_name=f"Démo {number + 1}",
                birth_date=date(today.year - 20, 1, 15),
                gender=Application.Gender.MALE,
                city="Abidjan",
                consent_given=True,
                consent_at=now,
                status=status,
                retention_until=retention,
            )
        for number in range(6):
            NewsletterSubscriber.objects.create(
                email=f"abonne{number}@{DEMO_DOMAIN}",
                is_confirmed=number < 5,
                confirmed_at=now if number < 5 else None,
                source="démonstration",
            )
