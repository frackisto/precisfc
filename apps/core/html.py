"""Texte enrichi (éditeur de l'administration) : ce qui est autorisé, et son assainissement.

Le même jeu de balises sert à l'éditeur (ce que l'on peut saisir) et au nettoyeur
nh3 (ce qui est conservé). L'assainissement a lieu à l'enregistrement **et** à
l'affichage : un contenu inséré autrement que par un formulaire (import, script,
modification directe en base) ne peut pas injecter de script non plus.
"""

import nh3
from django.utils.html import linebreaks
from django.utils.safestring import mark_safe

# Extensions de l'éditeur (django-prose-editor) : mise en forme simple, titres de
# niveau 2 et 3 (le niveau 1 est le titre de la page), listes, citations, liens.
EDITOR_EXTENSIONS = {
    "Bold": True,
    "Italic": True,
    "Underline": True,
    "Strike": True,
    "Heading": {"levels": [2, 3]},
    "BulletList": True,
    "OrderedList": True,
    "ListItem": True,
    "Blockquote": True,
    "HorizontalRule": True,
    "HardBreak": True,
    "Link": {"enableTarget": False},
}

ALLOWED_TAGS = {
    "p", "br", "strong", "em", "u", "s", "h2", "h3",
    "ul", "ol", "li", "blockquote", "hr", "a",
}  # fmt: skip
ALLOWED_ATTRIBUTES = {"a": {"href", "title"}, "ol": {"start"}}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto", "tel"}


def sanitize_html(value: str) -> str:
    """HTML réduit aux balises autorisées : ni script, ni style, ni attribut « on… »,
    ni lien « javascript: ». Les liens reçoivent rel="noopener noreferrer"."""
    if not value:
        return ""
    return nh3.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer",
        strip_comments=True,
    )


def render_rich_text(value: str) -> str:
    """HTML sûr à afficher. Un ancien texte brut (sans balise) garde ses paragraphes."""
    if not value:
        return ""
    if not nh3.is_html(value):
        # Texte échappé par linebreaks (autoescape) avant d'être entouré de <p>.
        return mark_safe(linebreaks(value, autoescape=True))  # noqa: S308
    return mark_safe(sanitize_html(value))  # noqa: S308  (nettoyé par nh3 juste avant)
