"""Médiathèque : validation des vidéos intégrées."""

import pytest
from django.core.exceptions import ValidationError

from apps.media_library.models import Album, Video
from tests.helpers import rejected_by_database

pytestmark = pytest.mark.django_db


def make_video(provider, video_id, **kwargs):
    return Video(
        title="Résumé du match", kind="MATCH", provider=provider, video_id=video_id, **kwargs
    )


@pytest.mark.parametrize(
    ("provider", "video_id", "embed_url"),
    [
        ("YOUTUBE", "dQw4w9WgXcQ", "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"),
        ("VIMEO", "76979871", "https://player.vimeo.com/video/76979871"),
        ("DAILYMOTION", "x8abc12", "https://www.dailymotion.com/embed/video/x8abc12"),
    ],
)
def test_valid_video_ids_give_an_embed_url(provider, video_id, embed_url):
    video = make_video(provider, video_id)

    video.full_clean()
    assert video.embed_url == embed_url


@pytest.mark.parametrize(
    ("provider", "video_id"),
    [
        ("YOUTUBE", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        ("YOUTUBE", '"><script>'),
        ("VIMEO", "abc"),
        ("DAILYMOTION", "8abc12"),
    ],
)
def test_urls_and_malformed_ids_are_rejected(provider, video_id):
    video = make_video(provider, video_id[:20])

    with pytest.raises(ValidationError, match="Identifiant"):
        video.full_clean()


def test_same_video_cannot_be_registered_twice():
    make_video("YOUTUBE", "dQw4w9WgXcQ").save()

    with rejected_by_database():
        make_video("YOUTUBE", "dQw4w9WgXcQ").save()


def test_album_slug_comes_from_title():
    album = Album.objects.create(title="Entraînement du 12 octobre", kind="TRAINING")

    assert album.slug == "entrainement-du-12-octobre"
