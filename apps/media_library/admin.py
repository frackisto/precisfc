from django.contrib import admin

from .models import Album, Photo, Video


class PhotoInline(admin.TabularInline):
    model = Photo
    extra = 0
    fields = ("image", "caption", "alt_text", "credit", "order")


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "event_date", "is_published", "published_at")
    list_filter = ("kind", "is_published", "season")
    search_fields = ("title",)
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("match",)
    inlines = [PhotoInline]


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "provider", "video_id", "is_published", "published_at")
    list_filter = ("kind", "provider", "is_published")
    search_fields = ("title", "video_id")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("match",)
