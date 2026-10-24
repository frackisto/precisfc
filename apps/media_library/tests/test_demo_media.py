"""Commande demo_media : albums et vidéos de démonstration."""

import pytest
from django.core.management import CommandError, call_command

from apps.media_library.models import Album, Photo, Video

pytestmark = pytest.mark.django_db


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.DEBUG = True
    return tmp_path


def test_creates_visible_albums_with_photos_and_videos(media, client):
    call_command("demo_media", verbosity=0)

    assert Album.objects.filter(slug__startswith="demo-", is_published=True).count() == 2
    assert Photo.objects.count() == 14
    assert Video.objects.filter(slug__startswith="demo-").count() == 3
    album = Album.objects.get(slug="demo-victoire-a-domicile")
    assert album.cover and album.photos.first().image.width == 1600
    assert client.get("/medias/").status_code == 200
    page = client.get(album.get_absolute_url()).content.decode()
    assert page.count("data-lightbox-item") == 8 and ".webp" in page


def test_running_twice_does_not_duplicate_files_or_rows(media):
    call_command("demo_media", verbosity=0)
    call_command("demo_media", verbosity=0)

    assert Album.objects.count() == 2 and Photo.objects.count() == 14 and Video.objects.count() == 3
    originals = list((media / "albums").rglob("*.jpg"))
    assert len(originals) == 14 + 2  # photos + couvertures, sans copie en double


def test_delete_keeps_real_content_and_removes_demo_files(media):
    real = Album.objects.create(title="Vrai album", kind="MATCH", is_published=True)
    call_command("demo_media", verbosity=0)

    call_command("demo_media", "--delete", verbosity=0)

    assert list(Album.objects.all()) == [real]
    assert not Video.objects.exists()
    assert not list((media / "albums").rglob("*.jpg"))


def test_refuses_to_run_outside_development(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError, match="développement"):
        call_command("demo_media", verbosity=0)
