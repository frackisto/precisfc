"""Commande demo_banners : bannières de démonstration et images provisoires."""

from io import BytesIO

import pytest
from django.core.files.storage import default_storage
from django.core.management import CommandError, call_command
from PIL import Image

from apps.core.models import HeroSlide

pytestmark = pytest.mark.django_db


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.DEBUG = True
    return tmp_path


def test_creates_four_visible_banners_with_full_hd_images(media, client):
    call_command("demo_banners", verbosity=0)

    slides = HeroSlide.objects.visible()
    assert slides.count() == 4
    first = slides.order_by("order").first()
    assert first.cta_url == "/club/"
    with default_storage.open(first.image.name) as image_file:
        assert Image.open(BytesIO(image_file.read())).size == (1920, 1080)
    page = client.get("/").content.decode()
    assert "Tous au stade samedi !" in page and "Rejoins l&#x27;académie Precis FC" in page


def test_running_twice_does_not_duplicate(media):
    call_command("demo_banners", verbosity=0)
    call_command("demo_banners", verbosity=0)

    assert HeroSlide.objects.count() == 4
    assert len(list((media / "hero" / "demo").iterdir())) == 4


def test_delete_removes_only_demo_banners_and_their_images(media):
    HeroSlide.objects.create(title="Vraie bannière", image="hero/vraie.jpg")
    call_command("demo_banners", verbosity=0)

    call_command("demo_banners", "--delete", verbosity=0)

    assert list(HeroSlide.objects.values_list("title", flat=True)) == ["Vraie bannière"]
    assert list((media / "hero" / "demo").iterdir()) == []


def test_refuses_to_run_outside_development(media, settings):
    settings.DEBUG = False

    with pytest.raises(CommandError, match="développement"):
        call_command("demo_banners", verbosity=0)
    assert HeroSlide.objects.count() == 0

    call_command("demo_banners", "--force", verbosity=0)
    assert HeroSlide.objects.count() == 4
