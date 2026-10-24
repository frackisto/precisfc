"""Médiathèque : albums, déclinaisons WebP, visionneuse, vidéos, envoi groupé de photos."""

from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.media_library.models import Album, Photo, Video
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def html(response):
    return response.content.decode()


def jpeg(name="photo.jpg", size=(1600, 1200)):
    buffer = BytesIO()
    Image.new("RGB", size, (201, 162, 39)).save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def test_index_lists_published_albums_and_videos_only(client):
    Album.objects.create(title="Victoire 3-0", kind="MATCH", is_published=True)
    Album.objects.create(title="Album caché", kind="MATCH")
    Album.objects.create(
        title="Album futur",
        kind="EVENT",
        is_published=True,
        published_at=timezone.now() + timedelta(days=1),
    )
    Video.objects.create(
        title="Résumé", kind="MATCH", provider="YOUTUBE", video_id="dQw4w9WgXcQ", is_published=True
    )

    page = html(client.get(reverse("media_library:index")))

    assert "Victoire 3-0" in page and "Résumé" in page
    assert "Album caché" not in page and "Album futur" not in page


def test_index_filters_by_kind(client):
    Album.objects.create(title="Victoire contre Bouaké", kind="MATCH", is_published=True)
    Album.objects.create(title="Séance du mardi", kind="TRAINING", is_published=True)

    page = html(client.get(reverse("media_library:index"), {"type": "TRAINING"}))

    assert "Séance du mardi" in page and "Victoire contre Bouaké" not in page


def test_album_shows_webp_thumbnails_linking_to_large_versions(client, media):
    album = Album.objects.create(title="Entraînement", kind="TRAINING", is_published=True)
    photo = Photo.objects.create(album=album, image=jpeg(), caption="Échauffement", credit="Club")

    page = html(client.get(album.get_absolute_url()))

    assert photo.thumb.url.endswith(".webp") and photo.thumb.url in page
    assert photo.large.url in page and "data-lightbox-item" in page
    assert "Échauffement — © Club" in page
    with Image.open(photo.thumb.path) as thumbnail:
        assert thumbnail.format == "WEBP" and thumbnail.size == (400, 300)
    with Image.open(photo.large.path) as large:
        assert large.size == (1600, 1200)  # jamais agrandie au-delà de l'original


def test_unpublished_album_returns_404(client):
    album = Album.objects.create(title="Caché", kind="MATCH")

    assert client.get(album.get_absolute_url()).status_code == 404


def test_video_page_embeds_the_privacy_friendly_player(client):
    video = Video.objects.create(
        title="Temps forts",
        kind="MATCH",
        provider="YOUTUBE",
        video_id="dQw4w9WgXcQ",
        is_published=True,
    )

    page = html(client.get(video.get_absolute_url()))

    assert 'src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"' in page
    assert '"@type": "VideoObject"' in page


def test_admin_bulk_upload_adds_valid_photos_and_rejects_fakes(client, media):
    client.force_login(UserFactory(is_superuser=True))
    album = Album.objects.create(title="Gala", kind="EVENT")
    url = reverse("admin:media_library_album_change", args=[album.pk])
    base = {
        "title": "Gala",
        "slug": album.slug,
        "kind": "EVENT",
        "photos-TOTAL_FORMS": "0",
        "photos-INITIAL_FORMS": "0",
    }
    fake = SimpleUploadedFile("photo.jpg", b"pas une image", content_type="image/jpeg")

    refused = client.post(url, {**base, "new_photos": [jpeg("a.jpg"), fake]})
    assert refused.status_code == 200 and "pas une image valide" in html(refused)
    assert album.photos.count() == 0

    accepted = client.post(url, {**base, "new_photos": [jpeg("a.jpg"), jpeg("b.jpg")]})
    assert accepted.status_code == 302
    assert list(album.photos.values_list("order", flat=True)) == [0, 1]


def test_sitemap_lists_published_albums_and_videos(client):
    album = Album.objects.create(title="Public", kind="MATCH", is_published=True)
    hidden = Album.objects.create(title="Privé", kind="MATCH")

    sitemap = html(client.get("/sitemap.xml"))

    assert album.get_absolute_url() in sitemap and hidden.get_absolute_url() not in sitemap


def test_menu_lists_news_and_media(client):
    page = html(client.get("/"))

    assert 'href="/actualites/"' in page and 'href="/medias/"' in page
