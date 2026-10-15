"""Réglages de production (cPanel LWS ; aussi valables sur un VPS).

Le durcissement complet (CSP, journalisation, check --deploy) est finalisé aux
étapes 3 et 15.
"""

from .base import *

DEBUG = False

# Nouveau dictionnaire pour ne pas modifier celui de base.py.
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --- HTTPS ----------------------------------------------------------------------
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Uniquement si un proxy en amont termine le TLS et transmet X-Forwarded-Proto.
if env.bool("DJANGO_TRUST_X_FORWARDED_PROTO", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HSTS : laissé à 0 tant que le HTTPS n'est pas validé (exigence du cahier des charges),
# puis activé via la variable d'environnement.
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = False
