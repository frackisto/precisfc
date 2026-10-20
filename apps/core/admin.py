from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from .models import (
    ClubSettings,
    Facility,
    FacilityPhoto,
    HeroSlide,
    OrgMember,
    Page,
    President,
    ScheduledJobRun,
    Trophy,
    TrophyWin,
    Value,
)

SEO_FIELDSET = (
    "Référencement",
    {"classes": ("collapse",), "fields": ("meta_title", "meta_description", "og_image")},
)


@admin.register(ScheduledJobRun)
class ScheduledJobRunAdmin(admin.ModelAdmin):
    list_display = ("name", "last_status", "last_started_at", "last_finished_at", "locked_until")
    list_filter = ("last_status",)
    readonly_fields = [field.name for field in ScheduledJobRun._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(ClubSettings)
class ClubSettingsAdmin(admin.ModelAdmin):
    """Une seule fiche : la liste mène directement au formulaire."""

    fieldsets = (
        ("Identité", {"fields": ("name", "short_name", "slogan", "founded_year", "about_short")}),
        ("Logos", {"fields": ("logo", "logo_dark", "favicon")}),
        ("Couleurs", {"fields": ("color_primary", "color_secondary", "color_light")}),
        (
            "Coordonnées",
            {"fields": ("home_stadium", "address", "phone", "email", "map_lat", "map_lng")},
        ),
        (
            "Réseaux sociaux",
            {
                "fields": (
                    "facebook_url",
                    "x_url",
                    "instagram_url",
                    "youtube_url",
                    "tiktok_url",
                    "linkedin_url",
                )
            },
        ),
        ("Référencement", {"fields": ("default_meta_description", "default_og_image")}),
    )

    def changelist_view(self, request, extra_context=None):
        settings_obj = ClubSettings.load()
        return redirect(reverse("admin:core_clubsettings_change", args=[settings_obj.pk]))

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class FacilityPhotoInline(admin.TabularInline):
    model = FacilityPhoto
    extra = 0


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "capacity", "order", "is_published")
    list_filter = ("kind", "is_published")
    list_editable = ("order", "is_published")
    search_fields = ("name", "address")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [FacilityPhotoInline]


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ("title", "order", "is_active", "starts_at", "ends_at")
    list_filter = ("is_active",)
    list_editable = ("order", "is_active")
    search_fields = ("title",)


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("title", "section", "order", "is_published", "updated_at")
    list_filter = ("section", "is_published")
    search_fields = ("title", "body")
    prepopulated_fields = {"slug": ("title",)}
    fieldsets = (
        (None, {"fields": ("section", "title", "slug", "cover", "body", "order", "is_published")}),
        SEO_FIELDSET,
    )


@admin.register(Value)
class ValueAdmin(admin.ModelAdmin):
    list_display = ("title", "icon", "order")
    list_editable = ("order",)


class TrophyWinInline(admin.TabularInline):
    model = TrophyWin
    extra = 0


@admin.register(Trophy)
class TrophyAdmin(admin.ModelAdmin):
    list_display = ("name", "competition_name", "category", "order")
    list_editable = ("order",)
    search_fields = ("name", "competition_name")
    inlines = [TrophyWinInline]


@admin.register(President)
class PresidentAdmin(admin.ModelAdmin):
    list_display = ("full_name", "start_year", "end_year", "order")
    search_fields = ("full_name",)


@admin.register(OrgMember)
class OrgMemberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "role_title", "department", "order", "is_published")
    list_filter = ("department", "is_published")
    list_editable = ("order", "is_published")
    search_fields = ("full_name", "role_title")
