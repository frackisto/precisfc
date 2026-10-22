"""Contrastes WCAG 2.1 des couleurs du thème (niveau AA : 4,5:1 pour le texte)."""

import pytest

from apps.core.colors import (
    AA_NORMAL_TEXT,
    BLACK,
    DARK_BODY_BG,
    LIGHT_BODY_BG,
    WHITE,
    contrast_ratio,
    hex_to_rgb,
    mix,
    readable_on,
    relative_luminance,
    text_color_for,
    theme_palette,
)

DEFAULTS = ("#0B1F3A", "#C9A227", "#F2F4F7")


def test_reference_contrast_values():
    assert contrast_ratio(WHITE, BLACK) == pytest.approx(21)
    assert contrast_ratio("#777777", WHITE) == pytest.approx(4.48, abs=0.01)
    assert relative_luminance(BLACK) == 0
    assert relative_luminance(WHITE) == pytest.approx(1)


def test_hex_parsing():
    assert hex_to_rgb("#0b1f3a") == (11, 31, 58)
    with pytest.raises(ValueError):
        hex_to_rgb("#FFF")


def test_text_color_follows_background():
    assert text_color_for("#0B1F3A") == WHITE
    assert text_color_for("#C9A227") == BLACK
    assert text_color_for("#FFFF00") == BLACK


def test_mix_goes_from_color_to_target():
    assert mix("#000000", "#FFFFFF", 0) == "#000000"
    assert mix("#000000", "#FFFFFF", 1) == "#FFFFFF"
    assert mix("#000000", "#FFFFFF", 0.5) == "#808080"


def test_readable_color_is_kept_when_already_readable():
    assert readable_on("#0B1F3A", WHITE) == "#0B1F3A"


@pytest.mark.parametrize("color", ["#FFFF00", "#C9A227", "#87CEEB", "#777777"])
def test_unreadable_color_is_adjusted_on_light_background(color):
    assert contrast_ratio(readable_on(color, LIGHT_BODY_BG), LIGHT_BODY_BG) >= AA_NORMAL_TEXT


@pytest.mark.parametrize("color", ["#0B1F3A", "#000080", "#8B0000", "#C9A227"])
def test_unreadable_color_is_adjusted_on_dark_background(color):
    assert contrast_ratio(readable_on(color, DARK_BODY_BG), DARK_BODY_BG) >= AA_NORMAL_TEXT


# Couleurs par défaut du club, puis des choix extrêmes qu'un administrateur pourrait faire.
PALETTES = [
    DEFAULTS,
    ("#FFD700", "#FFFFFF", "#EEEEEE"),
    ("#000000", "#111111", "#222222"),
    ("#E30613", "#009639", "#F7F7F7"),
    ("#777777", "#777777", "#777777"),
]


@pytest.mark.parametrize("colors", PALETTES, ids=lambda colors: "-".join(colors))
def test_every_text_of_the_theme_is_readable(colors):
    palette = theme_palette(*colors)

    pairs = {
        "texte sur fond principal": (palette["primary_text"], palette["primary"]),
        "texte sur fond d'accent": (palette["secondary_text"], palette["secondary"]),
        "texte sur fond clair": (palette["light_text"], palette["light"]),
        "liens en mode clair": (palette["link_light"], LIGHT_BODY_BG),
        "liens en mode sombre": (palette["link_dark"], DARK_BODY_BG),
        "accent sur fond principal": (palette["accent_on_primary"], palette["primary"]),
    }
    for label, (text, background) in pairs.items():
        assert contrast_ratio(text, background) >= AA_NORMAL_TEXT, label


def test_default_palette_keeps_club_colors_where_readable():
    palette = theme_palette(*DEFAULTS)

    assert palette["primary"] == "#0B1F3A"
    assert palette["link_light"] == "#0B1F3A"
    assert palette["accent_on_primary"] == "#C9A227"
    assert palette["primary_rgb"] == "11, 31, 58"
