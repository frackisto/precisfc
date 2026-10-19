#!/usr/bin/env python
"""Utilitaire en ligne de commande de Django."""

import os
import sys
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent / ".env"


def load_env_file(env_file=ENV_FILE):
    """Charge le fichier ``.env`` sans écraser les variables déjà définies.

    Permet au serveur d'imposer ``DJANGO_SETTINGS_MODULE=config.settings.prod``
    dans son ``.env`` : les réglages de développement ne sont alors jamais
    chargés par erreur, même sans ``export`` dans le terminal.
    """
    if env_file.exists():
        import environ

        environ.Env.read_env(env_file)


def main():
    try:
        load_env_file()
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django est introuvable. L'environnement virtuel est-il activé ?"
        ) from exc
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
