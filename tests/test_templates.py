"""Contrôles sur tous les gabarits du projet."""

from pathlib import Path

import pytest
from django.conf import settings
from django.template.loader import get_template

TEMPLATES_DIR = Path(settings.BASE_DIR) / "templates"
TEMPLATES = sorted(
    path.relative_to(TEMPLATES_DIR).as_posix()
    for path in TEMPLATES_DIR.rglob("*")
    if path.suffix in {".html", ".css", ".txt"}
)


@pytest.mark.parametrize("name", TEMPLATES)
def test_template_compiles(name):
    get_template(name)


@pytest.mark.parametrize("name", TEMPLATES)
def test_short_comments_fit_on_one_line(name):
    # Un commentaire {# … #} sur plusieurs lignes s'afficherait tel quel dans la page :
    # utiliser {% comment %} … {% endcomment %}.
    lines = (TEMPLATES_DIR / name).read_text(encoding="utf-8").splitlines()
    unclosed = [
        number for number, line in enumerate(lines, 1) if line.count("{#") > line.count("#}")
    ]

    assert unclosed == [], f"{name}, lignes {unclosed}"
