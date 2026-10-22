"""Couleurs du thème : contrastes WCAG 2.1 et ajustements automatiques.

Les couleurs du club se changent dans l'administration ; ces fonctions garantissent
que le texte reste lisible (contraste d'au moins 4,5:1, niveau AA) en mode clair comme
en mode sombre.
"""

WHITE = "#FFFFFF"
BLACK = "#000000"
# Fonds utilisés par Bootstrap 5.3 (variables --bs-body-bg).
LIGHT_BODY_BG = WHITE
DARK_BODY_BG = "#212529"
AA_NORMAL_TEXT = 4.5


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Couleur hexadécimale attendue (#RRGGBB) : {color!r}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def relative_luminance(color: str) -> float:
    def channel(value: int) -> float:
        srgb = value / 255
        return srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(value) for value in hex_to_rgb(color))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def text_color_for(background: str) -> str:
    """Blanc ou noir, selon ce qui se lit le mieux sur ``background``."""
    return (
        WHITE if contrast_ratio(background, WHITE) >= contrast_ratio(background, BLACK) else BLACK
    )


def mix(color: str, target: str, weight: float) -> str:
    """Mélange ``color`` avec ``target`` (``weight`` = part de ``target``, de 0 à 1)."""
    start, end = hex_to_rgb(color), hex_to_rgb(target)
    return rgb_to_hex(tuple(round(a + (b - a) * weight) for a, b in zip(start, end, strict=True)))


def readable_on(color: str, background: str, minimum: float = AA_NORMAL_TEXT) -> str:
    """``color`` éclaircie ou assombrie juste assez pour se lire sur ``background``."""
    if contrast_ratio(color, background) >= minimum:
        return color
    # Vers le blanc ou le noir : celui des deux qui contraste le plus (toujours ≥ 4,58:1).
    target = text_color_for(background)
    for step in range(1, 21):
        candidate = mix(color, target, step / 20)
        if contrast_ratio(candidate, background) >= minimum:
            return candidate
    return target


def theme_palette(primary: str, secondary: str, light: str) -> dict[str, str]:
    """Toutes les couleurs dont la feuille de style du thème a besoin."""
    link_light = readable_on(primary, LIGHT_BODY_BG)
    link_dark = readable_on(secondary, DARK_BODY_BG)
    return {
        "primary": primary.upper(),
        "primary_rgb": _rgb_string(primary),
        "primary_text": text_color_for(primary),
        "primary_hover": mix(primary, BLACK, 0.15),
        "secondary": secondary.upper(),
        "secondary_rgb": _rgb_string(secondary),
        "secondary_text": text_color_for(secondary),
        "secondary_hover": mix(secondary, BLACK, 0.15),
        "light": light.upper(),
        "light_text": text_color_for(light),
        # Liens : la couleur du club si elle est lisible, sinon une variante ajustée.
        "link_light": link_light,
        "link_light_rgb": _rgb_string(link_light),
        "link_dark": link_dark,
        "link_dark_rgb": _rgb_string(link_dark),
        # Accent posé sur la couleur principale (menu, bandeau d'accueil).
        "accent_on_primary": readable_on(secondary, primary),
    }


def _rgb_string(color: str) -> str:
    return ", ".join(str(value) for value in hex_to_rgb(color))
