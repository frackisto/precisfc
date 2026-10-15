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

# --- Journalisation dans des fichiers (LOG_DIR, hors de public_html) -------------
LOG_DIR.mkdir(parents=True, exist_ok=True)
_file_handler = {
    "class": "logging.handlers.RotatingFileHandler",
    "formatter": "verbose",
    "maxBytes": 5 * 1024 * 1024,
    "backupCount": 5,
    "encoding": "utf-8",
}
LOGGING = {
    **LOGGING,
    "handlers": {
        **LOGGING["handlers"],
        "file": {**_file_handler, "filename": str(LOG_DIR / "django.log")},
        "errors_file": {**_file_handler, "filename": str(LOG_DIR / "errors.log"), "level": "ERROR"},
    },
    "root": {"handlers": ["file", "errors_file"], "level": LOG_LEVEL},
    "loggers": {
        "django": {
            "handlers": ["file", "errors_file", "mail_admins"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "apps": {"handlers": ["file", "errors_file"], "level": LOG_LEVEL, "propagate": False},
    },
}
