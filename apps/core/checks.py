"""Contrôles système propres au projet (``python manage.py check``)."""

from pathlib import Path

from django.conf import settings
from django.core.checks import Error, Tags, register
from django.db import connections

UTF8MB4 = "utf8mb4"


def charset_errors(charset: str, database_name: str) -> list[Error]:
    if charset == UTF8MB4:
        return []
    return [
        Error(
            f"La base « {database_name} » utilise le jeu de caractères {charset} "
            f"au lieu de {UTF8MB4} : les accents et emojis seraient corrompus.",
            hint=(
                f"ALTER DATABASE `{database_name}` CHARACTER SET utf8mb4 "
                "COLLATE utf8mb4_unicode_ci;  (avant le premier migrate)"
            ),
            id="core.E001",
        )
    ]


def engine_errors(non_innodb_tables: list[tuple[str, str]], database_name: str) -> list[Error]:
    if not non_innodb_tables:
        return []
    listing = ", ".join(f"{table} ({engine})" for table, engine in non_innodb_tables)
    return [
        Error(
            f"Tables non InnoDB dans « {database_name} » : {listing}. Sans InnoDB, il n'y a "
            "ni transactions ni verrous de ligne (risque de doubles réservations).",
            hint="ALTER TABLE <table> ENGINE=InnoDB;  ou recréer la base vide puis migrate.",
            id="core.E003",
        )
    ]


@register(Tags.database)
def check_database_charset_and_engine(app_configs, databases=None, **kwargs):
    """Vérifie que la base est en utf8mb4 et que toutes ses tables sont InnoDB.

    Le serveur LWS est en latin1 par défaut et WAMP crée des tables MyISAM.
    Exécuté seulement avec ``check --database default``.
    """
    errors = []
    for alias in databases or []:
        connection = connections[alias]
        if connection.vendor != "mysql":
            continue
        with connection.cursor() as cursor:
            cursor.execute("SELECT @@character_set_database")
            (charset,) = cursor.fetchone()
            cursor.execute(
                "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE' "
                "AND ENGINE <> 'InnoDB' ORDER BY TABLE_NAME"
            )
            non_innodb = list(cursor.fetchall())
        name = connection.settings_dict["NAME"]
        errors += charset_errors(charset, name)
        errors += engine_errors(non_innodb, name)
    return errors


def _is_within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


@register(Tags.security)
def check_private_media_is_not_public(app_configs, **kwargs):
    """Le stockage privé ne doit jamais se trouver dans un dossier servi publiquement."""
    private = Path(settings.PRIVATE_MEDIA_ROOT).resolve()
    errors = []
    for setting_name in ("MEDIA_ROOT", "STATIC_ROOT"):
        public = Path(getattr(settings, setting_name)).resolve()
        if _is_within(private, public) or _is_within(public, private):
            errors.append(
                Error(
                    f"PRIVATE_MEDIA_ROOT ({private}) chevauche {setting_name} ({public}).",
                    hint="Placer les fichiers privés hors de public_html, "
                    "ex. /home/<compte>/precisfc_private.",
                    id="core.E002",
                )
            )
    return errors
