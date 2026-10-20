"""Conventions du schéma (docs/01-proposition-architecture.md §3)."""

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import models

from apps.core.models import TimeStampedModel

PROJECT_APPS = [
    "core",
    "accounts",
    "teams",
    "competitions",
    "matches",
    "news",
    "media_library",
    "shop",
    "orders",
    "payments",
    "ticketing",
    "academy",
    "partners",
    "contact",
    "notifications",
    "dashboard",
]

PROJECT_MODELS = [
    model
    for model in apps.get_models()
    if model.__module__.startswith("apps.") and not model._meta.auto_created
]

# Exceptions justifiées à l'héritage de TimeStampedModel.
NOT_TIMESTAMPED = {"accounts.user", "core.scheduledjobrun"}


def test_the_sixteen_project_apps_are_installed():
    installed = {
        config.label for config in apps.get_app_configs() if config.name.startswith("apps.")
    }

    assert installed == set(PROJECT_APPS)


@pytest.mark.parametrize("model", PROJECT_MODELS, ids=lambda model: model._meta.label)
def test_models_are_timestamped(model):
    if model._meta.label_lower in NOT_TIMESTAMPED:
        pytest.skip("Exception documentée")
    assert issubclass(model, TimeStampedModel)


@pytest.mark.parametrize("model", PROJECT_MODELS, ids=lambda model: model._meta.label)
def test_models_have_french_names_and_readable_str(model):
    assert "verbose_name" in model._meta.original_attrs
    assert "verbose_name_plural" in model._meta.original_attrs
    assert model.__str__ is not models.Model.__str__


@pytest.mark.parametrize("model", PROJECT_MODELS, ids=lambda model: model._meta.label)
def test_amounts_are_twelve_digit_decimals(model):
    for field in model._meta.get_fields():
        if isinstance(field, models.DecimalField) and field.name not in {
            "lat",
            "lng",
            "map_lat",
            "map_lng",
        }:
            assert (field.max_digits, field.decimal_places) == (12, 2), field.name


@pytest.mark.parametrize("model", PROJECT_MODELS, ids=lambda model: model._meta.label)
def test_indexed_text_columns_fit_innodb_limits(model):
    # 255 caractères utf8mb4 maximum pour une colonne indexée (§3, points propres à MySQL).
    for field in model._meta.get_fields():
        if isinstance(field, models.CharField) and (field.unique or field.db_index):
            assert field.max_length <= 255, field.name


@pytest.mark.django_db
def test_no_missing_migrations():
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)


@pytest.mark.parametrize("model", PROJECT_MODELS, ids=lambda model: model._meta.label)
def test_no_partial_unique_constraints(model):
    # MariaDB ne crée pas ces contraintes (avertissement models.W036, masqué pour allauth).
    for constraint in model._meta.constraints:
        assert getattr(constraint, "condition", None) is None or isinstance(
            constraint, models.CheckConstraint
        ), constraint.name
