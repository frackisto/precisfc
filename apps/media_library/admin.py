from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from apps.core.validators import validate_image_upload

from .models import Album, Photo, Video

MAX_PHOTOS_PER_UPLOAD = 50


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    """Plusieurs images en un envoi, chacune validée (poids, format, contenu réel)."""

    widget = MultipleImageInput(attrs={"accept": "image/jpeg,image/png,image/webp,image/gif"})

    def clean(self, data, initial=None):
        files = [file for file in (data or []) if file]
        if len(files) > MAX_PHOTOS_PER_UPLOAD:
            raise ValidationError(f"{MAX_PHOTOS_PER_UPLOAD} photos au plus par envoi.")
        errors = []
        for file in files:
            try:
                validate_image_upload(file)
            except ValidationError as error:
                errors.append(f"{file.name} : {' '.join(error.messages)}")
        if errors:
            raise ValidationError(errors)
        return files


class AlbumAdminForm(forms.ModelForm):
    new_photos = MultipleImageField(
        label="Ajouter des photos",
        required=False,
        help_text=f"Sélection multiple possible ({MAX_PHOTOS_PER_UPLOAD} au plus).",
    )

    class Meta:
        model = Album
        fields = "__all__"  # noqa: DJ007  (champs choisis par les fieldsets de AlbumAdmin)


class PhotoInline(admin.TabularInline):
    model = Photo
    extra = 0
    fields = ("image", "caption", "alt_text", "credit", "order")


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    form = AlbumAdminForm
    list_display = ("title", "kind", "event_date", "is_published", "published_at")
    list_filter = ("kind", "is_published", "season")
    search_fields = ("title",)
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("match",)
    inlines = [PhotoInline]
    fieldsets = (
        (None, {"fields": ("title", "slug", "kind", "season", "match", "event_date", "cover")}),
        ("Publication", {"fields": ("is_published", "published_at")}),
        ("Photos", {"fields": ("new_photos",)}),
    )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        album = form.instance
        start = album.photos.count()
        for order, file in enumerate(form.cleaned_data.get("new_photos", []), start=start):
            Photo.objects.create(album=album, image=file, order=order)


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "provider", "video_id", "is_published", "published_at")
    list_filter = ("kind", "provider", "is_published")
    search_fields = ("title", "video_id")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("match",)
