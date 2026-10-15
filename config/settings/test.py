"""Réglages des tests automatisés (pytest).

Les tests utilisent la même base MariaDB que le développement (base ``test_precisfc``
créée et détruite automatiquement), pour que les verrous et contraintes soient réels.
"""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "insecure-test-only-key")  # noqa: S105

from .base import *  # noqa: E402

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]

# Hachage rapide : seuls les tests en profitent, jamais la production.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Pas de collectstatic avant les tests : WhiteNoise cherche les fichiers à la demande.
WHITENOISE_AUTOREFRESH = True
