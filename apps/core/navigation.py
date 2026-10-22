"""Menu principal du site.

Chaque rubrique n'apparaît que lorsque sa page existe (URL résolue) : le menu se
complète tout seul au fil des étapes, sans jamais afficher de lien mort.
"""

from dataclasses import dataclass

from django.urls import NoReverseMatch, reverse


@dataclass(frozen=True)
class MenuItem:
    label: str
    url_name: str
    icon: str


MAIN_MENU = [
    MenuItem("Accueil", "core:home", "house-door"),
    MenuItem("Le club", "core:club", "shield"),
    MenuItem("Équipes", "teams:list", "people"),
    MenuItem("Matchs", "matches:list", "calendar-event"),
    MenuItem("Actualités", "news:list", "newspaper"),
    MenuItem("Médias", "media_library:index", "images"),
    MenuItem("Boutique", "shop:index", "bag"),
    MenuItem("Billetterie", "ticketing:index", "ticket-perforated"),
    MenuItem("Académie", "academy:index", "mortarboard"),
    MenuItem("Partenaires", "partners:list", "award"),
    MenuItem("Contact", "contact:index", "envelope"),
]


def build_menu(current_path: str, items=MAIN_MENU) -> list[dict]:
    menu = []
    for item in items:
        try:
            url = reverse(item.url_name)
        except NoReverseMatch:
            continue
        is_active = current_path == url if url == "/" else current_path.startswith(url)
        menu.append({"label": item.label, "url": url, "icon": item.icon, "active": is_active})
    return menu
