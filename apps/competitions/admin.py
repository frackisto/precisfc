from django.contrib import admin

from .models import (
    Club,
    Competition,
    CompetitionSeason,
    Participation,
    PlayerSeasonStat,
    Season,
    Standing,
)


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_current")
    list_filter = ("is_current",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "city", "country", "is_own_club")
    list_filter = ("is_own_club", "country")
    search_fields = ("name", "short_name", "city")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "country", "has_standings")
    list_filter = ("kind", "has_standings")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class ParticipationInline(admin.TabularInline):
    model = Participation
    extra = 0
    autocomplete_fields = ("club",)


@admin.register(CompetitionSeason)
class CompetitionSeasonAdmin(admin.ModelAdmin):
    list_display = ("competition", "season", "team")
    list_filter = ("season", "competition__kind", "team")
    search_fields = ("competition__name", "season__name")
    list_select_related = ("competition", "season", "team")
    inlines = [ParticipationInline]


class ComputedAdmin(admin.ModelAdmin):
    """Tables recalculées automatiquement : consultation seule."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Standing)
class StandingAdmin(ComputedAdmin):
    list_display = (
        "position",
        "club",
        "competition_season",
        "played",
        "won",
        "drawn",
        "lost",
        "goal_difference",
        "points",
    )
    list_filter = ("competition_season",)
    list_select_related = ("club", "competition_season__competition", "competition_season__season")


@admin.register(PlayerSeasonStat)
class PlayerSeasonStatAdmin(ComputedAdmin):
    list_display = ("player", "competition_season", "appearances", "goals", "assists", "minutes")
    list_filter = ("season", "competition_season")
    search_fields = ("player__first_name", "player__last_name")
    list_select_related = (
        "player",
        "competition_season__competition",
        "competition_season__season",
    )
