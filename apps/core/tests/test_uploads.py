"""Validation des images téléversées : poids, format, contenu réel, dimensions."""

from io import BytesIO

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import models
from PIL import Image

from apps.core.validators import validate_image_upload


def image_file(name="photo.jpg", size=(800, 600), image_format="JPEG"):
    buffer = BytesIO()
    Image.new("RGB", size, (11, 31, 58)).save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


@pytest.mark.parametrize(
    ("name", "image_format"), [("a.jpg", "JPEG"), ("a.png", "PNG"), ("a.webp", "WEBP")]
)
def test_valid_images_are_accepted(name, image_format):
    validate_image_upload(image_file(name, image_format=image_format))


def test_too_heavy_file_is_refused(settings):
    settings.MAX_UPLOAD_SIZE = 1024

    with pytest.raises(ValidationError, match="trop lourd"):
        validate_image_upload(image_file(size=(800, 600)))


def test_wrong_extension_is_refused():
    with pytest.raises(ValidationError, match="Format non accepté"):
        validate_image_upload(image_file("photo.svg"))


def test_text_file_renamed_as_image_is_refused():
    fake = SimpleUploadedFile(
        "photo.jpg", b"<?php system($_GET['c']); ?>", content_type="image/jpeg"
    )

    with pytest.raises(ValidationError, match="pas une image valide"):
        validate_image_upload(fake)


def test_extension_must_not_lie_about_the_format():
    disguised = image_file("photo.jpg", image_format="BMP")

    with pytest.raises(ValidationError, match="Format non accepté"):
        validate_image_upload(disguised)


def test_gigantic_image_is_refused():
    huge = image_file("immense.png", size=(9000, 6000), image_format="PNG")

    with pytest.raises(ValidationError, match="trop grande"):
        validate_image_upload(huge)


def test_files_already_stored_are_not_checked_again():
    class StoredFile:
        _committed = True

    validate_image_upload(StoredFile())


def test_every_project_image_field_is_validated():
    unvalidated = [
        f"{model._meta.label}.{field.name}"
        for model in apps.get_models()
        if model.__module__.startswith("apps.")
        for field in model._meta.get_fields()
        if isinstance(field, models.ImageField) and validate_image_upload not in field.validators
    ]

    assert unvalidated == []
