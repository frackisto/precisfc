"""Statistiques des joueurs d'une édition, recalculées depuis les feuilles de match.

- Match joué : titulaire, ou remplaçant effectivement entré en jeu.
- Minutes : de l'entrée (0 pour un titulaire) à la sortie (remplacement ou carton
  rouge), 90 sinon. Le temps additionnel n'est pas compté.
- Buts : buts et penalties marqués (pas les buts contre son camp).
- Second carton jaune : compte un jaune et un rouge.
- Match sans encaisser : gardien titulaire resté sur le terrain tout le match, son
  équipe n'ayant encaissé aucun but.
"""

from collections import defaultdict

from django.db import transaction
from django.db.models import Prefetch

from apps.competitions.models import CompetitionSeason, PlayerSeasonStat
from apps.matches.models import LineupEntry, Match, MatchEvent, Side
from apps.teams.models import Player

FULL_MATCH = 90
FIELDS = (
    "appearances",
    "starts",
    "minutes",
    "goals",
    "assists",
    "yellow_cards",
    "red_cards",
    "clean_sheets",
)


def _conceded(match: Match, side: str) -> int:
    return match.away_score if side == Side.HOME else match.home_score


def compute_player_stats(edition: CompetitionSeason) -> dict[int, dict[str, int]]:
    stats = defaultdict(lambda: dict.fromkeys(FIELDS, 0))
    matches = (
        Match.objects.filter(competition_season=edition, status=Match.Status.FINISHED)
        .exclude(home_score__isnull=True)
        .prefetch_related(
            Prefetch(
                "lineup",
                queryset=LineupEntry.objects.filter(player__isnull=False).select_related("player"),
            ),
            Prefetch("events", queryset=MatchEvent.objects.order_by("minute", "added_time")),
        )
    )
    for match in matches:
        subbed_in, left_at = {}, {}
        for event in match.events.all():
            kind = event.kind
            if kind == MatchEvent.Kind.SUBSTITUTION:
                if event.player_id:
                    subbed_in[event.player_id] = event.minute
                if event.player_out_id:
                    left_at.setdefault(event.player_out_id, event.minute)
            elif kind in (MatchEvent.Kind.GOAL, MatchEvent.Kind.PENALTY_GOAL) and event.player_id:
                stats[event.player_id]["goals"] += 1
            if (
                kind in (MatchEvent.Kind.GOAL, MatchEvent.Kind.PENALTY_GOAL)
                and event.assist_player_id
            ):
                stats[event.assist_player_id]["assists"] += 1
            if event.player_id and kind in (MatchEvent.Kind.YELLOW, MatchEvent.Kind.SECOND_YELLOW):
                stats[event.player_id]["yellow_cards"] += 1
            if event.player_id and kind in (MatchEvent.Kind.RED, MatchEvent.Kind.SECOND_YELLOW):
                stats[event.player_id]["red_cards"] += 1
                left_at.setdefault(event.player_id, event.minute)

        for entry in match.lineup.all():
            player_id = entry.player_id
            start = 0 if entry.is_starter else subbed_in.get(player_id)
            if start is None:  # remplaçant resté sur le banc
                continue
            end = min(left_at.get(player_id, FULL_MATCH), FULL_MATCH)
            line = stats[player_id]
            line["appearances"] += 1
            line["starts"] += entry.is_starter
            line["minutes"] += max(0, end - start)
            played_whole_match = entry.is_starter and player_id not in left_at
            if (
                played_whole_match
                and entry.player.position == Player.Position.GK
                and _conceded(match, entry.side) == 0
            ):
                line["clean_sheets"] += 1
    return stats


@transaction.atomic
def update_player_stats(edition: CompetitionSeason) -> int:
    CompetitionSeason.objects.select_for_update().filter(pk=edition.pk).exists()
    PlayerSeasonStat.objects.filter(competition_season=edition).delete()
    rows = [
        PlayerSeasonStat(
            player_id=player_id,
            competition_season=edition,
            season_id=edition.season_id,
            **values,
        )
        for player_id, values in compute_player_stats(edition).items()
    ]
    PlayerSeasonStat.objects.bulk_create(rows)
    return len(rows)
