from datetime import date

import pytest

from apps.partners.models import Partner
from tests.helpers import rejected_by_database

pytestmark = pytest.mark.django_db


def test_partnership_cannot_end_before_it_starts():
    with rejected_by_database():
        Partner.objects.create(
            name="Banque partenaire",
            logo="partners/logo.png",
            tier=Partner.Tier.MAIN,
            starts_on=date(2026, 9, 1),
            ends_on=date(2026, 8, 31),
        )


def test_partner_slug_and_ordering_by_tier():
    media = Partner.objects.create(name="Radio Côte", logo="p/a.png", tier=Partner.Tier.MEDIA)
    main = Partner.objects.create(name="Opérateur", logo="p/b.png", tier=Partner.Tier.MAIN)

    assert media.slug == "radio-cote"
    assert list(Partner.objects.all()) == [main, media]
