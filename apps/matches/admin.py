from django.contrib import admin

from apps.accounts.permissions import can_change_match

from .models import LineupEntry, Match, MatchEvent, MatchScheduleChange, MatchTeamStat


class MatchChildInline(admin.TabularInline):
    """Compositions, événements, statistiques : modifiables seulement si le match l'est."""

    def _parent_allowed(self, request, obj):
        return obj is None or can_change_match(request.user, obj)

    def has_add_permission(self, request, obj=None):
        return self._parent_allowed(request, obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._parent_allowed(request, obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._parent_allowed(request, obj) and super().has_delete_permission(request, obj)


class LineupEntryInline(MatchChildInline):
    model = LineupEntry
    extra = 0
    autocomplete_fields = ("player",)


class MatchEventInline(MatchChildInline):
    model = MatchEvent
    extra = 0
    autocomplete_fields = ("player", "assist_player", "player_out")


class MatchTeamStatInline(MatchChildInline):
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

    def has_change_permission(self, request, obj=None):
        # Un entraîneur ne saisit que les matchs de son équipe ; les autres sont en lecture.
        if obj is None:
            return super().has_change_permission(request)
        return can_change_match(request.user, obj)

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
