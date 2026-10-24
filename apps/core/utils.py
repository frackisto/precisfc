"""Outils communs aux modèles de toutes les applications."""

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import PurePosixPath

from django.utils import timezone
from django.utils.deconstruct import deconstructible
from django.utils.text import slugify


def unique_slug(instance, source: str, *, field_name: str = "slug") -> str:
    """Slug dérivé de ``source``, rendu unique par un suffixe -2, -3… si nécessaire."""
    max_length = instance._meta.get_field(field_name).max_length
    base = slugify(source)[:max_length].strip("-") or "element"
    others = type(instance)._default_manager.exclude(pk=instance.pk)

    candidate, number = base, 2
    while others.filter(**{field_name: candidate}).exists():
        suffix = f"-{number}"
        candidate = f"{base[: max_length - len(suffix)].rstrip('-')}{suffix}"
        number += 1
    return candidate


def years_ago(years: int, today: date | None = None) -> date:
    """Date d'il y a ``years`` ans (le 29 février devient le 28 les années non bissextiles)."""
    today = today or timezone.localdate()
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today.replace(year=today.year - years, day=28)


def age_on(birth_date: date, today: date | None = None) -> int:
    """Âge révolu à la date ``today`` (par défaut aujourd'hui, fuseau du club)."""
    today = today or timezone.localdate()
    return (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )


@deconstructible
class RandomFilename:
    """``upload_to`` qui remplace le nom d'origine par un identifiant aléatoire.

    Le nom choisi par l'internaute (souvent son nom ou celui de l'enfant) n'apparaît
    ainsi jamais sur le disque ; il est conservé à part si nécessaire.
    """

    def __init__(self, prefix: str):
        self.prefix = prefix.strip("/")

    def __call__(self, instance, filename: str) -> str:
        extension = PurePosixPath(filename).suffix.lower()[:10]
        today = timezone.localdate()
        return f"{self.prefix}/{today:%Y/%m}/{uuid.uuid4().hex}{extension}"

    def __eq__(self, other):
        return isinstance(other, RandomFilename) and self.prefix == other.prefix


# Espace insécable : un montant ne se coupe jamais en fin de ligne (« 15 000 FCFA »).
NBSP = chr(0xA0)


def format_fcfa(amount, *, with_unit: bool = True) -> str:
    """Montant en francs CFA, sans décimales et groupé par milliers : « 15 000 FCFA »."""
    if amount is None or amount == "":
        return ""
    rounded = int(Decimal(amount).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    text = f"{rounded:,}".replace(",", NBSP)
    return f"{text}{NBSP}FCFA" if with_unit else text
