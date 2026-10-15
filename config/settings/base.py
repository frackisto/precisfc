"""Réglages communs à tous les environnements.

Les valeurs propres à chaque machine (secrets, base de données, hôtes) proviennent
des variables d'environnement ou du fichier ``.env`` (voir ``.env.example``).
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
if (BASE_DIR / ".env").exists():
    environ.Env.read_env(BASE_DIR / ".env")

# --- Sécurité de base ---------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
# URL de l'administration Django : à rendre non devinable en production.
ADMIN_URL = env("DJANGO_ADMIN_URL", default="admin/")

# --- Applications -------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
# Les applications tierces sont ajoutées à l'étape où elles sont utilisées.
THIRD_PARTY_APPS: list[str] = []
LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
]

# Modèle utilisateur personnalisé (connexion par e-mail) : défini avant le premier migrate.
AUTH_USER_MODEL = "accounts.User"
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Base de données (MariaDB / MySQL) ----------------------------------------
# Exemple : mysql://utilisateur:motdepasse@127.0.0.1:3307/precisfc
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["OPTIONS"] = {
    # Le serveur LWS est en latin1 par défaut : on impose utf8mb4 à chaque connexion.
    "charset": "utf8mb4",
    # InnoDB imposé : WAMP crée les tables en MyISAM par défaut (ni transactions ni
    # verrous de ligne, donc aucune protection contre les doubles réservations).
    "init_command": (
        "SET default_storage_engine=INNODB, "
        "sql_mode='STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'"
    ),
    "isolation_level": "read committed",
}
DATABASES["default"]["TEST"] = {
    "NAME": env("TEST_DATABASE_NAME", default="test_precisfc"),
    "CHARSET": "utf8mb4",
    "COLLATION": "utf8mb4_unicode_ci",
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Mots de passe ------------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Langue et fuseau horaire (Côte d'Ivoire) ---------------------------------
LANGUAGE_CODE = "fr"
LANGUAGES = [("fr", "Français")]
TIME_ZONE = "Africa/Abidjan"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

# --- Fichiers statiques et médias ---------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = Path(env("STATIC_ROOT", default=str(BASE_DIR / "staticfiles")))
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))
# Fichiers jamais servis directement par le serveur web (candidatures, pièces jointes).
# En production : hors de public_html (contrôle système core.E002).
PRIVATE_MEDIA_ROOT = Path(env("PRIVATE_MEDIA_ROOT", default=str(BASE_DIR / "private_media")))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "private": {"BACKEND": "apps.core.storage.PrivateStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# --- Téléversements -----------------------------------------------------------
# Taille maximale d'un fichier téléversé, appliquée par les validateurs des formulaires.
MAX_UPLOAD_SIZE = env.int("MAX_UPLOAD_SIZE_MB", default=8) * 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

# --- Cache ----------------------------------------------------------------------
# cPanel : table en base (partagée entre les processus Passenger).
# VPS : CACHE_URL=redis://127.0.0.1:6379/1
CACHES = {"default": env.cache("CACHE_URL", default="dbcache://django_cache")}

# --- Tâches asynchrones (Celery) ------------------------------------------------
# cPanel n'autorise pas de worker permanent : les tâches s'exécutent immédiatement
# (mode « eager »). Sur VPS : CELERY_TASK_ALWAYS_EAGER=False + CELERY_BROKER_URL=redis://…
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=True)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="memory://")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "Africa/Abidjan"
CELERY_TASK_TIME_LIMIT = 300

# --- E-mails --------------------------------------------------------------------
# LWS : EMAIL_URL=smtp+ssl://contact%40domaine.ci:motdepasse@mail.domaine.ci:465
vars().update(env.email("EMAIL_URL", default="consolemail://"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Precis FC <no-reply@localhost>")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
EMAIL_TIMEOUT = 15
# Destinataires des alertes d'erreur 500 (adresses séparées par des virgules).
ADMINS = [("Admin", email) for email in env.list("DJANGO_ADMINS", default=[])]

# --- Journalisation -------------------------------------------------------------
LOG_LEVEL = env("DJANGO_LOG_LEVEL", default="INFO")
LOG_DIR = Path(env("LOG_DIR", default=str(BASE_DIR / "logs")))
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} [pid {process}] {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "mail_admins": {
            "class": "django.utils.log.AdminEmailHandler",
            "level": "ERROR",
            "filters": ["require_debug_false"],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console", "mail_admins"], "level": LOG_LEVEL, "propagate": False},
        "apps": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

# --- En-têtes de sécurité communs ---------------------------------------------
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
