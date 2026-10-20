"""Outils communs aux tests."""

from contextlib import contextmanager

import pytest
from django.db import DataError, IntegrityError, transaction


@contextmanager
def rejected_by_database():
    """Vérifie que MariaDB refuse l'écriture (contrainte CHECK, unicité ou colonne non signée).

    Les écritures passent par ``objects.create()`` ou ``update()``, qui ne valident pas
    les formulaires : c'est bien la base qui doit protéger les données.
    """
    with pytest.raises((IntegrityError, DataError)), transaction.atomic():
        yield
