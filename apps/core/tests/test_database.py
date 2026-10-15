"""Tests de la base MariaDB : jeu de caractères, moteur InnoDB, transactions."""

import pytest
from django.core.management import call_command
from django.db import connection, transaction

from apps.accounts.models import User
from apps.core.checks import charset_errors, engine_errors

pytestmark = pytest.mark.django_db


def test_connection_uses_utf8mb4_and_innodb():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT @@character_set_database, @@character_set_connection, @@default_storage_engine"
        )
        database_charset, connection_charset, engine = cursor.fetchone()

    assert database_charset == "utf8mb4"
    assert connection_charset == "utf8mb4"
    assert engine == "InnoDB"


def test_every_project_table_is_innodb():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE' "
            "AND ENGINE <> 'InnoDB'"
        )
        assert cursor.fetchall() == ()


def test_database_system_checks_pass():
    call_command("check", databases=["default"], fail_level="WARNING")


def test_accents_and_emoji_survive_a_round_trip():
    user = User.objects.create_user("ebrie@precis.ci", first_name="Kouamé ⚽ Ébrié")
    user.refresh_from_db()

    assert user.first_name == "Kouamé ⚽ Ébrié"


def test_rolled_back_transaction_leaves_no_trace():
    # Avec MyISAM, l'écriture survivrait au rollback : ce test garantit InnoDB.
    with pytest.raises(RuntimeError), transaction.atomic():
        User.objects.create_user("rollback@precis.ci")
        raise RuntimeError("annulation")

    assert not User.objects.filter(email="rollback@precis.ci").exists()


def test_charset_check_flags_latin1_database():
    errors = charset_errors("latin1", "compte_precisfc")

    assert [error.id for error in errors] == ["core.E001"]
    assert "utf8mb4" in errors[0].hint
    assert charset_errors("utf8mb4", "compte_precisfc") == []


def test_engine_check_flags_myisam_tables():
    errors = engine_errors([("django_session", "MyISAM")], "precisfc")

    assert [error.id for error in errors] == ["core.E003"]
    assert "django_session (MyISAM)" in errors[0].msg
    assert engine_errors([], "precisfc") == []
