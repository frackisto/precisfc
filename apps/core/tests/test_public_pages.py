"""Accueil et pages du club : contenus affichés ou masqués, nombre de requêtes borné."""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    ClubSettings,
    Facility,
    HeroSlide,
    OrgMember,
    Page,
    President,
    Trophy,
    TrophyWin,
    Value,
)
from apps.core.utils import years_ago
from apps.news.models import Article
from apps.partners.models import Partner
from tests.factories import ClubFactory, MatchFactory, PlayerFactory

pytestmark = pytest.mark.django_db


def html(response):
    return response.content.decode()


@pytest.fixture
def own_club():
    return ClubFactory(name="Precis FC", is_own_club=True)


# --- Accueil -------------------------------------------------------------------------


def test_empty_home_page_shows_the_club_name(client):
    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert '<h1 class="display-4 fw-bold">Precis FC</h1>' in html(response)


def test_home_shows_only_banners_currently_displayed(client):
    now = timezone.now()
    HeroSlide.objects.create(title="Bienvenue au stade", image="hero/a.jpg")
    HeroSlide.objects.create(title="Bannière désactivée", image="hero/b.jpg", is_active=False)
    HeroSlide.objects.create(
        title="Bannière expirée",
        image="hero/c.jpg",
        starts_at=now - timedelta(days=10),
        ends_at=now - timedelta(days=1),
    )
    HeroSlide.objects.create(
        title="Bannière à venir", image="hero/d.jpg", starts_at=now + timedelta(days=1)
    )

    page = html(client.get(reverse("core:home")))

    assert "Bienvenue au stade" in page
    assert "désactivée" not in page and "expirée" not in page and "à venir" not in page


def test_home_shows_next_match_and_last_result_of_our_club(client, own_club):
    now = timezone.now()
    MatchFactory(home_club=own_club, away_club=ClubFactory(name="ASEC Mimosas"))
    MatchFactory(
        away_club=own_club,
        home_club=ClubFactory(name="Africa Sports"),
        kickoff_at=now - timedelta(days=7),
        status="FINISHED",
        home_score=1,
        away_score=3,
    )
    MatchFactory(home_club=ClubFactory(name="Match entre adversaires"))
    MatchFactory(home_club=own_club, away_club=ClubFactory(name="Match masqué"), is_published=False)

    page = html(client.get(reverse("core:home")))

    assert "Prochain match" in page and "ASEC Mimosas" in page
    assert "Dernier résultat" in page and "Africa Sports" in page and "1 – 3" in page
    assert "Match entre adversaires" not in page
    assert "Match masqué" not in page


def test_home_lists_only_published_articles(client):
    now = timezone.now()
    Article.objects.create(title="Victoire à domicile", status="PUBLISHED", publish_at=now)
    Article.objects.create(
        title="Programmé et passé", status="SCHEDULED", publish_at=now - timedelta(minutes=5)
    )
    Article.objects.create(title="Brouillon secret", status="DRAFT")
    Article.objects.create(
        title="Programmé demain", status="SCHEDULED", publish_at=now + timedelta(days=1)
    )

    page = html(client.get(reverse("core:home")))

    assert "Victoire à domicile" in page and "Programmé et passé" in page
    assert "Brouillon secret" not in page and "Programmé demain" not in page


def test_home_never_shows_a_minor_without_consent(client):
    PlayerFactory(first_name="Adulte", is_featured=True)
    PlayerFactory(first_name="Mineur", birth_date=years_ago(15), is_featured=True)

    page = html(client.get(reverse("core:home")))

    assert "Adulte" in page
    assert "Mineur" not in page


def test_home_lists_only_current_partners(client):
    today = timezone.localdate()
    Partner.objects.create(name="Partenaire actuel", logo="p/a.png", tier="MAIN")
    Partner.objects.create(
        name="Ancien partenaire", logo="p/b.png", tier="MAIN", ends_on=today - timedelta(days=1)
    )
    Partner.objects.create(name="Partenaire inactif", logo="p/c.png", tier="MAIN", is_active=False)

    page = html(client.get(reverse("core:home")))

    assert 'alt="Partenaire actuel"' in page
    assert "Ancien partenaire" not in page and "Partenaire inactif" not in page


def test_home_query_count_does_not_grow_with_content(
    client, own_club, django_assert_max_num_queries
):
    now = timezone.now()
    for number in range(8):
        HeroSlide.objects.create(title=f"Bannière {number}", image=f"hero/{number}.jpg")
        Article.objects.create(title=f"Article {number}", status="PUBLISHED", publish_at=now)
        PlayerFactory(is_featured=True)
        Partner.objects.create(name=f"Partenaire {number}", logo="p/x.png", tier="OFFICIAL")
        MatchFactory(home_club=own_club, kickoff_at=now + timedelta(days=number + 1))
    client.get(reverse("core:home"))  # met les paramètres du club en cache

    with django_assert_max_num_queries(10):
        response = client.get(reverse("core:home"))

    assert response.status_code == 200


# --- Pages du club ------------------------------------------------------------------------


def test_club_page_lists_published_pages_and_values(client):
    Page.objects.create(section="HISTORY", title="Notre histoire", is_published=True)
    Page.objects.create(section="OTHER", title="Page en préparation")
    Value.objects.create(title="Solidarité", icon="people")

    page = html(client.get(reverse("core:club")))

    assert 'href="/club/notre-histoire/"' in page
    assert "Page en préparation" not in page
    assert "Solidarité" in page


def test_menu_now_shows_the_club_section(client):
    assert 'href="/club/"' in html(client.get(reverse("core:home")))


def test_published_page_is_displayed_with_escaped_text(client):
    Page.objects.create(
        section="HISTORY",
        title="Histoire",
        body="Fondé en 1985.\n\n<script>alert('x')</script>",
        is_published=True,
    )

    page = html(client.get(reverse("core:page_detail", args=["histoire"])))

    assert "Fondé en 1985." in page
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page


def test_unpublished_or_unknown_page_returns_404(client):
    Page.objects.create(section="HISTORY", title="Brouillon")

    assert client.get(reverse("core:page_detail", args=["brouillon"])).status_code == 404
    assert client.get(reverse("core:page_detail", args=["inconnue"])).status_code == 404


def test_fixed_club_routes_take_precedence_over_page_slugs(client):
    Page.objects.create(section="OTHER", title="Palmares", is_published=True)

    assert "Palmarès" in html(client.get("/club/palmares/"))


def test_trophies_page_lists_titles_won(client):
    league = Trophy.objects.create(name="Championnat national")
    TrophyWin.objects.create(trophy=league, year=2019, season_label="2018-2019")
    TrophyWin.objects.create(trophy=league, year=2022)
    Trophy.objects.create(name="Coupe jamais gagnée")

    page = html(client.get(reverse("core:trophies")))

    assert "Championnat national" in page and "× 2" in page
    assert "2018-2019" in page and "2022" in page
    assert "Coupe jamais gagnée" not in page


def test_presidents_page(client):
    President.objects.create(full_name="Jean Koffi", start_year=2010, end_year=2018)
    President.objects.create(full_name="Awa Traoré", start_year=2018)

    page = html(client.get(reverse("core:presidents")))

    assert "2010 – 2018" in page
    assert "2018 – aujourd’hui" in page


def test_organisation_chart_groups_by_department_and_hides_unpublished(client):
    OrgMember.objects.create(
        full_name="A. Président", role_title="Président", department="DIRECTION"
    )
    OrgMember.objects.create(full_name="B. Médecin", role_title="Médecin", department="MEDICAL")
    OrgMember.objects.create(
        full_name="C. Caché", role_title="X", department="MEDICAL", is_published=False
    )

    page = html(client.get(reverse("core:organisation")))

    assert "Direction" in page and "Médical" in page
    assert "C. Caché" not in page


def test_facility_detail_with_map_link(client):
    stadium = Facility.objects.create(
        name="Stade Robert Champroux",
        kind="STADIUM",
        capacity=20000,
        lat="5.316667",
        lng="-4.033333",
    )
    Facility.objects.create(name="Projet secret", kind="OFFICE", is_published=False)

    listing = html(client.get(reverse("core:facilities")))
    detail = html(client.get(stadium.get_absolute_url()))

    assert "Stade Robert Champroux" in listing and "Projet secret" not in listing
    assert "20000 places" in detail
    assert "openstreetmap.org/?mlat=5.316667&amp;mlon=-4.033333" in detail
    assert client.get(reverse("core:facility_detail", args=["projet-secret"])).status_code == 404


def test_club_settings_stadium_and_founding_year_on_club_page(client):
    club = ClubSettings.load()
    club.founded_year = 1985
    club.home_stadium = Facility.objects.create(name="Stade municipal", kind="STADIUM")
    club.save()

    page = html(client.get(reverse("core:club")))

    assert "1985" in page and "Stade municipal" in page


def test_dates_are_displayed_in_french(client, own_club):
    MatchFactory(
        home_club=own_club,
        kickoff_at=timezone.make_aware(
            timezone.datetime.combine(
                date.today() + timedelta(days=30), timezone.datetime.min.time()
            )
        ),
    )

    page = html(client.get(reverse("core:home")))

    months = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]  # fmt: skip
    assert any(month in page for month in months)
