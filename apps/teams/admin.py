from django.contrib import admin

from .models import Player, PlayerPhoto, Staff, Team


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "gender", "season", "head_coach", "order", "is_published")
    list_filter = ("category", "gender", "is_published", "season")
    list_editable = ("order", "is_published")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("head_coach",)


class PlayerPhotoInline(admin.TabularInline):
    model = PlayerPhoto
    extra = 0


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "team",
        "shirt_number",
        "position",
        "birth_date",
        "publication_consent",
        "is_featured",
        "is_published",
    )
    list_filter = ("team", "position", "is_published", "is_featured", "publication_consent")
    search_fields = ("first_name", "last_name")
    list_select_related = ("team",)
    inlines = [PlayerPhotoInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    ("first_name", "last_name"),
                    "slug",
                    "team",
                    ("shirt_number", "position", "detailed_position"),
                    "photo",
                    "bio",
                )
            },
        ),
        (
            "Informations personnelles",
            {
                "fields": (
                    ("birth_date", "nationality"),
                    ("height_cm", "weight_kg", "preferred_foot"),
                    "joined_on",
                )
            },
        ),
        (
            "Publication et confidentialité",
            {
                "description": (
                    "Un joueur mineur n'apparaît sur le site qu'avec le consentement de son "
                    "représentant légal ; seule son année de naissance est alors affichée."
                ),
                "fields": (
                    ("is_published", "is_featured"),
                    ("show_birth_date", "show_physical"),
                    ("publication_consent", "consent_by", "consent_date"),
                ),
            },
        ),
    )


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ("full_name", "role", "team", "order", "is_published")
    list_filter = ("role", "team", "is_published")
    search_fields = ("first_name", "last_name")
    list_select_related = ("team",)
    autocomplete_fields = ("user",)
