"""Le stockage privé ne doit jamais être accessible par une URL publique."""

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import storages

from apps.core.checks import check_private_media_is_not_public


@pytest.fixture
def private_storage(settings, tmp_path):
    settings.STORAGES = {
        **settings.STORAGES,
        "private": {
            "BACKEND": "apps.core.storage.PrivateStorage",
            "OPTIONS": {"location": tmp_path},
        },
    }
    return storages["private"]


def test_private_files_are_saved_outside_public_folders(private_storage, tmp_path):
    name = private_storage.save("candidatures/acte-naissance.pdf", ContentFile(b"%PDF-1.4"))

    assert (tmp_path / name).exists()


def test_private_files_have_no_public_url(private_storage):
    name = private_storage.save("candidatures/certificat.pdf", ContentFile(b"%PDF-1.4"))

    with pytest.raises(NotImplementedError):
        private_storage.url(name)


def test_private_files_cannot_be_downloaded_by_path(client, private_storage):
    name = private_storage.save("candidatures/photo.jpg", ContentFile(b"jpeg"))

    for url in (f"/private_media/{name}", f"/media/../private_media/{name}"):
        assert client.get(url).status_code == 404


def test_default_private_root_is_outside_public_folders():
    assert check_private_media_is_not_public(None) == []


def test_private_root_inside_media_root_is_an_error(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "public_html" / "media"
    settings.PRIVATE_MEDIA_ROOT = tmp_path / "public_html" / "media" / "prive"

    errors = check_private_media_is_not_public(None)

    assert [error.id for error in errors] == ["core.E002"]
