"""Modèles communs : slugs, paramètres du club (singleton), contraintes."""

from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import ClubSettings, Facility, HeroSlide, Page, President
from apps.core.utils import RandomFilename, age_on, years_ago
from tests.helpers import rejected_by_database

pytestmark = pytest.mark.django_db


def test_slug_is_generated_from_source_without_accents():
    page = Page.objects.create(section=Page.Section.HISTORY, title="Notre histoire : 1985 à 2026")

    assert page.slug == "notre-histoire-1985-a-2026"


def test_duplicate_slugs_get_a_numbered_suffix():
    first = Facility.objects.create(name="Stade Félix", kind=Facility.Kind.STADIUM)
    second = Facility.objects.create(name="Stade Félix", kind=Facility.Kind.STADIUM)
    third = Facility.objects.create(name="Stade  félix", kind=Facility.Kind.STADIUM)

    assert (first.slug, second.slug, third.slug) == (
        "stade-felix",
        "stade-felix-2",
        "stade-felix-3",
    )


def test_slug_is_kept_when_the_title_changes():
    page = Page.objects.create(section=Page.Section.MISSION, title="Mission")
    page.title = "Mission et valeurs"
    page.save()

    page.refresh_from_db()
    assert page.slug == "mission"


def test_longest_titles_keep_unique_slugs_within_column_size():
    long_title = "x" * 200
    Page.objects.create(section=Page.Section.OTHER, title=long_title)
    duplicate = Page.objects.create(section=Page.Section.OTHER, title=long_title)

    assert duplicate.slug == f"{long_title}-2"
    assert len(duplicate.slug) <= Page._meta.get_field("slug").max_length


def test_slug_falls_back_when_source_has_no_letters():
    page = Page.objects.create(section=Page.Section.OTHER, title="!!!")

    assert page.slug == "element"


def test_club_settings_is_a_singleton_with_defaults():
    settings_obj = ClubSettings.load()
    again = ClubSettings.load()

    assert settings_obj.pk == again.pk == 1
    assert settings_obj.name == "Precis FC"
    assert settings_obj.currency == "XOF"
    assert settings_obj.color_primary == "#0B1F3A"


def test_club_settings_save_never_creates_a_second_row():
    ClubSettings.load()
    ClubSettings(name="Autre club").save()

    assert ClubSettings.objects.count() == 1
    assert ClubSettings.load().name == "Autre club"


def test_club_settings_rejects_invalid_colour():
    settings_obj = ClubSettings.load()
    settings_obj.color_primary = "bleu"

    with pytest.raises(ValidationError, match="hexadécimal"):
        settings_obj.full_clean()


def test_hero_slide_must_end_after_it_starts():
    now = timezone.now()

    with rejected_by_database():
        HeroSlide.objects.create(title="Bienvenue", image="hero/a.jpg", starts_at=now, ends_at=now)


def test_president_term_cannot_end_before_it_starts():
    with rejected_by_database():
        President.objects.create(full_name="Jean Koffi", start_year=2010, end_year=2005)


def test_years_ago_handles_leap_day():
    assert years_ago(18, today=date(2028, 2, 29)) == date(2010, 2, 28)
    assert years_ago(18, today=date(2026, 10, 19)) == date(2008, 10, 19)


def test_age_on_counts_completed_years():
    birthday = date(2008, 10, 20)

    assert age_on(birthday, today=date(2026, 10, 19)) == 17
    assert age_on(birthday, today=date(2026, 10, 20)) == 18


def test_random_filename_hides_the_original_name():
    upload_to = RandomFilename("academy/applications")

    path = upload_to(None, "Acte de naissance KONÉ Awa.PDF")

    assert path.startswith(f"academy/applications/{timezone.localdate():%Y/%m}/")
    assert path.endswith(".pdf")
    assert "KON" not in path
    assert upload_to(None, "a.pdf") != upload_to(None, "a.pdf")


def test_random_filename_is_serializable_for_migrations():
    assert RandomFilename("contact") == RandomFilename("contact")
    assert RandomFilename("contact").deconstruct()[2] == {}


def test_facility_capacity_cannot_be_negative():
    with rejected_by_database():
        Facility.objects.create(name="Stade", kind=Facility.Kind.STADIUM, capacity=-1)


def test_hero_slide_without_dates_is_allowed():
    slide = HeroSlide.objects.create(title="Saison 2026-2027", image="hero/b.jpg")

    assert slide.pk is not None
    assert slide.starts_at is None


def test_web_addresses_without_scheme_default_to_https():
    form_field = ClubSettings._meta.get_field("facebook_url").formfield()

    assert form_field.clean("facebook.com/precisfc") == "https://facebook.com/precisfc"
