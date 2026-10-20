from django.contrib import admin

from .models import LineupEntry, Match, MatchEvent, MatchScheduleChange, MatchTeamStat


class LineupEntryInline(admin.TabularInline):
    model = LineupEntry
    extra = 0
    autocomplete_fields = ("player",)


class MatchEventInline(admin.TabularInline):
    model = MatchEvent
    extra = 0
    autocomplete_fields = ("player", "assist_player", "player_out")


class MatchTeamStatInline(admin.TabularInline):
    model = MatchTeamStat
    extra = 0
    max_num = 2


class MatchScheduleChangeInline(admin.TabularInline):
    model = MatchScheduleChange
    extra = 0
    readonly_fields = ("old_kickoff_at", "new_kickoff_at", "reason", "changed_by", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "competition_season",
        "kickoff_at",
        "status",
        "home_score",
        "away_score",
        "is_published",
    )
    list_filter = ("status", "competition_season__season", "competition_season__competition")
    search_fields = ("home_club__name", "away_club__name", "round_label")
    date_hierarchy = "kickoff_at"
    list_select_related = (
        "home_club",
        "away_club",
        "competition_season__competition",
        "competition_season__season",
    )
    autocomplete_fields = ("home_club", "away_club")
    inlines = [LineupEntryInline, MatchEventInline, MatchTeamStatInline, MatchScheduleChangeInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "competition_season",
                    ("matchday", "round_label"),
                    ("home_club", "away_club"),
                    ("kickoff_at", "original_kickoff_at"),
                    ("venue", "venue_name"),
                    "status",
                    "slug",
                    "is_published",
                )
            },
        ),
        (
            "Score",
            {"fields": (("home_score", "away_score"), ("home_penalties", "away_penalties"))},
        ),
        (
            "Arbitrage et affluence",
            {
                "classes": ("collapse",),
                "fields": ("referee", "assistant_referees", "fourth_official", "attendance"),
            },
        ),
        ("Après-match", {"fields": ("report", "highlights_video")}),
    )
