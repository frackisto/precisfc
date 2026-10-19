"""Tests de l'étape 2 : configuration du projet et compatibilité des dépendances."""

import importlib
import os
import sys

import django
import pytest
from django.conf import settings
from django.core.management import call_command

from config.db_driver import install_mysql_driver
from config.settings import base


def test_django_is_the_pinned_lts_version():
    assert django.VERSION[:2] == (5, 2)


def test_python_matches_lws_minor_version():
    # LWS propose Python 3.13 : le poste de développement doit être aligné.
    assert sys.version_info[:2] == (3, 13)


def test_locale_and_timezone_target_cote_divoire():
    assert settings.LANGUAGE_CODE == "fr"
    assert settings.TIME_ZONE == "Africa/Abidjan"
    assert settings.USE_TZ is True


def test_production_hasher_is_argon2():
    assert base.PASSWORD_HASHERS[0] == "django.contrib.auth.hashers.Argon2PasswordHasher"


def test_database_is_mysql_family_with_utf8mb4():
    db = settings.DATABASES["default"]

    assert db["ENGINE"] == "django.db.backends.mysql"
    assert db["OPTIONS"]["charset"] == "utf8mb4"
    assert "STRICT_TRANS_TABLES" in db["OPTIONS"]["init_command"]
    assert db["TEST"]["COLLATION"] == "utf8mb4_unicode_ci"


def test_mysqlclient_is_used_when_available():
    assert install_mysql_driver() == "mysqlclient"


def test_pymysql_fallback_when_mysqlclient_is_missing(monkeypatch):
    # Simule un serveur où mysqlclient n'a pas pu être compilé.
    monkeypatch.setitem(sys.modules, "MySQLdb", None)

    assert install_mysql_driver() == "pymysql"
    assert sys.modules["MySQLdb"].__name__ == "pymysql"


def test_tests_never_run_in_debug():
    assert settings.DEBUG is False


@pytest.mark.parametrize("module", ["config.settings.dev", "config.settings.prod"])
def test_all_settings_modules_import(module):
    importlib.import_module(module)


def test_production_settings_are_secure_by_default():
    prod = importlib.import_module("config.settings.prod")

    assert prod.DEBUG is False
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
    assert prod.SECURE_SSL_REDIRECT is True
    assert "debug_toolbar" not in prod.INSTALLED_APPS


def test_environment_settings_do_not_mutate_base():
    # Charger dev puis prod ne doit rien ajouter aux objets partagés de base.py.
    importlib.import_module("config.settings.dev")
    importlib.import_module("config.settings.prod")

    assert "debug_toolbar" not in base.INSTALLED_APPS
    assert not any("debug_toolbar" in m for m in base.MIDDLEWARE)
    assert "whitenoise" not in base.STORAGES["staticfiles"]["BACKEND"]


def test_passenger_entry_point_exposes_wsgi_application():
    passenger = importlib.import_module("passenger_wsgi")

    assert callable(passenger.application)


def test_manage_py_takes_settings_module_from_env_file(tmp_path, monkeypatch):
    # Sur le serveur, le .env impose prod : dev (et debug_toolbar) n'est jamais chargé.
    manage = importlib.import_module("manage")
    env_file = tmp_path / ".env"
    env_file.write_text("DJANGO_SETTINGS_MODULE=config.settings.prod\n", encoding="utf-8")
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE")

    manage.load_env_file(env_file)

    assert os.environ["DJANGO_SETTINGS_MODULE"] == "config.settings.prod"


def test_manage_py_env_file_does_not_override_existing_variable(tmp_path, monkeypatch):
    manage = importlib.import_module("manage")
    env_file = tmp_path / ".env"
    env_file.write_text("DJANGO_SETTINGS_MODULE=config.settings.prod\n", encoding="utf-8")
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.test")

    manage.load_env_file(env_file)

    assert os.environ["DJANGO_SETTINGS_MODULE"] == "config.settings.test"


def test_custom_user_model_is_configured():
    assert settings.AUTH_USER_MODEL == "accounts.User"


def test_django_system_checks_pass():
    call_command("check", fail_level="WARNING")
