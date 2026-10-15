"""Réglages de développement (poste Windows + WAMP)."""

from .base import *

DEBUG = True
ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1"]

# Nouvelles listes (et non +=/insert) pour ne jamais modifier celles de base.py.
INSTALLED_APPS = [*INSTALLED_APPS, "debug_toolbar"]
# Après SecurityMiddleware et WhiteNoise, avant tout le reste.
MIDDLEWARE = [*MIDDLEWARE[:2], "debug_toolbar.middleware.DebugToolbarMiddleware", *MIDDLEWARE[2:]]
INTERNAL_IPS = ["127.0.0.1"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
