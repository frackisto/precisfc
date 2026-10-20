"""Centre de formation : représentant légal, consentement, documents privés."""

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from apps.academy.models import AgeCategory, Application, ApplicationDocument
from apps.core.storage import PrivateStorage
from apps.core.utils import years_ago
from tests.factories import ApplicationFactory
from tests.helpers import rejected_by_database

pytestmark = pytest.mark.django_db


def test_minor_application_requires_a_legal_guardian():
    application = ApplicationFactory.build(birth_date=years_ago(14))

    with pytest.raises(ValidationError) as excinfo:
        application.full_clean()

    assert set(excinfo.value.message_dict) >= set(Application.GUARDIAN_FIELDS)


def test_minor_application_with_guardian_is_valid():
    application = ApplicationFactory.build(
        birth_date=years_ago(14),
        guardian_name="Fatou Diabaté",
        guardian_relationship="Mère",
        guardian_phone="0505060708",
    )

    application.full_clean()


def test_adult_application_does_not_require_a_guardian():
    ApplicationFactory.build(birth_date=years_ago(19)).full_clean()


def test_application_requires_consent():
    with rejected_by_database():
        ApplicationFactory(consent_given=False, consent_at=None)


def test_age_category_years_must_be_ordered():
    with rejected_by_database():
        AgeCategory.objects.create(name="U15", min_birth_year=2013, max_birth_year=2011)


def test_documents_use_private_storage_and_random_names(tmp_path):
    document_field = ApplicationDocument._meta.get_field("file")
    assert isinstance(document_field.storage, PrivateStorage)

    document = ApplicationDocument(
        application=ApplicationFactory(),
        kind=ApplicationDocument.Kind.BIRTH_CERTIFICATE,
        original_name="Acte naissance Moussa.pdf",
    )
    document.file.storage = PrivateStorage(location=tmp_path)
    document.file.save("Acte naissance Moussa.pdf", ContentFile(b"%PDF-1.4"))

    assert "Moussa" not in document.file.name
    assert document.file.name.startswith("academy/applications/")
    assert (tmp_path / document.file.name).exists()
    with pytest.raises(NotImplementedError):
        document.file.url  # noqa: B018
