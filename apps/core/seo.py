"""Référencement : métadonnées de chaque page et données structurées Schema.org.

Une vue décrit sa page avec ``page_seo(...)`` ; ce qu'elle ne précise pas est repris
des paramètres du club (description et image de partage par défaut).
"""

from dataclasses import dataclass

from django.utils.html import strip_tags
from django.utils.text import Truncator

from .models import ClubSettings

DESCRIPTION_LENGTH = 160


@dataclass(frozen=True)
class Seo:
    title: str
    description: str
    canonical_url: str
    image_url: str = ""
    type: str = "website"
    noindex: bool = False


def _absolute_media(request, image) -> str:
    return request.build_absolute_uri(image.url) if image else ""


def summarize(text: str, length: int = DESCRIPTION_LENGTH) -> str:
    """Texte brut d'au plus ``length`` caractères (balises HTML retirées)."""
    plain = " ".join(strip_tags(text or "").split())
    return Truncator(plain).chars(length, truncate="…")


def page_seo(
    request,
    *,
    title: str = "",
    description: str = "",
    image=None,
    obj=None,
    type: str = "website",
    noindex: bool = False,
) -> Seo:
    """Métadonnées d'une page. ``obj`` : objet avec des champs SEO (meta_title…)."""
    club = ClubSettings.cached()
    if obj is not None:
        title = getattr(obj, "meta_title", "") or title
        description = getattr(obj, "meta_description", "") or description
        image = getattr(obj, "og_image", None) or image
    return Seo(
        title=title or club.name,
        description=summarize(description or club.default_meta_description or club.about_short),
        canonical_url=request.build_absolute_uri(request.path),
        image_url=_absolute_media(request, image or club.default_og_image or club.logo),
        type=type,
        noindex=noindex,
    )


def organization_jsonld(request, club) -> dict:
    """Le club pour les moteurs de recherche (type SportsTeam de Schema.org)."""
    data = {
        "@context": "https://schema.org",
        "@type": "SportsTeam",
        "name": club.name,
        "sport": "Football",
        "url": request.build_absolute_uri("/"),
    }
    if club.logo:
        data["logo"] = _absolute_media(request, club.logo)
    if club.founded_year:
        data["foundingDate"] = str(club.founded_year)
    if club.email:
        data["email"] = club.email
    if club.phone:
        data["telephone"] = club.phone
    if club.address:
        data["address"] = {
            "@type": "PostalAddress",
            "streetAddress": club.address,
            "addressCountry": "CI",
        }
    same_as = [
        url
        for url in (
            club.facebook_url,
            club.x_url,
            club.instagram_url,
            club.youtube_url,
            club.tiktok_url,
            club.linkedin_url,
        )
        if url
    ]
    if same_as:
        data["sameAs"] = same_as
    return data


def breadcrumbs_jsonld(request, crumbs) -> dict:
    """Fil d'Ariane (liste de (libellé, url), accueil compris automatiquement)."""
    items = [("Accueil", "/"), *crumbs]
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": position,
                "name": label,
                "item": request.build_absolute_uri(url or request.path),
            }
            for position, (label, url) in enumerate(items, start=1)
        ],
    }
