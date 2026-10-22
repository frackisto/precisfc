"""Calcul du classement d'une édition (championnat, phase de poules).

Règles :
- seuls les matchs terminés entre deux participants d'un même groupe comptent ;
- points = victoires × points_win + nuls × points_draw + défaites × points_loss
  + ajustement (pénalité ou bonus, motivé dans Participation) ;
- à égalité de points, les critères de ``Competition.tiebreak_rules`` s'appliquent
  dans l'ordre. Les critères « confrontations directes » sont calculés uniquement entre
  les clubs encore à égalité (mini-classement), comme dans les règlements de la CAF ;
- en dernier recours, l'ordre alphabétique rend le classement stable (jamais aléatoire).
"""

from collections import defaultdict
from dataclasses import dataclass, field

from django.db import transaction

from apps.competitions.models import CompetitionSeason, Standing, TiebreakRule
from apps.matches.models import Match

FORM_LENGTH = 5
WIN, DRAW, LOSS = "V", "N", "D"


@dataclass
class Row:
    club_id: int
    club_name: str
    group: str
    adjustment: int = 0
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    away_goals_for: int = 0
    points: int = 0
    results: list[str] = field(default_factory=list)

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    @property
    def form(self) -> str:
        return "".join(self.results[-FORM_LENGTH:])


@dataclass(frozen=True)
class Result:
    home_id: int
    away_id: int
    home_score: int
    away_score: int


def _outcome(scored: int, conceded: int) -> str:
    return WIN if scored > conceded else DRAW if scored == conceded else LOSS


def _head_to_head(rows: list[Row], results: list[Result], points) -> dict[int, tuple]:
    """Points, différence et buts de chaque club dans les matchs entre ``rows`` seuls."""
    ids = {row.club_id for row in rows}
    table = {club_id: [0, 0, 0] for club_id in ids}  # points, différence, buts marqués
    for result in results:
        if result.home_id in ids and result.away_id in ids:
            for club_id, scored, conceded in (
                (result.home_id, result.home_score, result.away_score),
                (result.away_id, result.away_score, result.home_score),
            ):
                table[club_id][0] += points[_outcome(scored, conceded)]
                table[club_id][1] += scored - conceded
                table[club_id][2] += scored
    return {club_id: tuple(values) for club_id, values in table.items()}


def _criterion(rule: str, rows: list[Row], results: list[Result], points) -> dict[int, int]:
    """Valeur de chaque club pour un critère (plus grand = mieux classé)."""
    if rule.startswith("head_to_head_"):
        h2h = _head_to_head(rows, results, points)
        index = {
            TiebreakRule.HEAD_TO_HEAD_POINTS: 0,
            TiebreakRule.HEAD_TO_HEAD_GOAL_DIFFERENCE: 1,
            TiebreakRule.HEAD_TO_HEAD_GOALS_FOR: 2,
        }[rule]
        return {row.club_id: h2h[row.club_id][index] for row in rows}
    attribute = {
        "points": "points",
        TiebreakRule.GOAL_DIFFERENCE: "goal_difference",
        TiebreakRule.GOALS_FOR: "goals_for",
        TiebreakRule.WINS: "won",
        TiebreakRule.AWAY_GOALS_FOR: "away_goals_for",
    }[rule]
    return {row.club_id: getattr(row, attribute) for row in rows}


def rank(rows: list[Row], rules: list[str], results: list[Result], points) -> list[Row]:
    """Ordonne les lignes : points, puis chaque critère, appliqué aux seuls ex aequo."""
    criteria = ["points", *rules]

    def resolve(subset: list[Row], depth: int) -> list[Row]:
        if len(subset) <= 1 or depth == len(criteria):
            return sorted(subset, key=lambda row: row.club_name.lower())
        values = _criterion(criteria[depth], subset, results, points)
        ordered = []
        for value in sorted(set(values.values()), reverse=True):
            tied = [row for row in subset if values[row.club_id] == value]
            ordered += resolve(tied, depth + 1)
        return ordered

    return resolve(rows, 0)


def compute_standings(edition: CompetitionSeason) -> list[tuple[int, Row]]:
    """Classement calculé, sans l'enregistrer : liste de (rang, ligne) par groupe."""
    competition = edition.competition
    points = {
        WIN: competition.points_win,
        DRAW: competition.points_draw,
        LOSS: competition.points_loss,
    }
    rows = {
        participation.club_id: Row(
            club_id=participation.club_id,
            club_name=participation.club.name,
            group=participation.group_name,
            adjustment=participation.points_adjustment,
        )
        for participation in edition.participations.select_related("club")
    }
    results_by_group = defaultdict(list)
    matches = (
        Match.objects.filter(
            competition_season=edition,
            status=Match.Status.FINISHED,
            home_score__isnull=False,
            away_score__isnull=False,
        )
        .order_by("kickoff_at", "pk")
        .values_list("home_club_id", "away_club_id", "home_score", "away_score")
    )
    for home_id, away_id, home_score, away_score in matches:
        home, away = rows.get(home_id), rows.get(away_id)
        if home is None or away is None or home.group != away.group:
            continue
        results_by_group[home.group].append(Result(home_id, away_id, home_score, away_score))
        for row, scored, conceded, is_away in (
            (home, home_score, away_score, False),
            (away, away_score, home_score, True),
        ):
            outcome = _outcome(scored, conceded)
            row.played += 1
            row.goals_for += scored
            row.goals_against += conceded
            row.away_goals_for += scored if is_away else 0
            row.won += outcome == WIN
            row.drawn += outcome == DRAW
            row.lost += outcome == LOSS
            row.results.append(outcome)

    by_group = defaultdict(list)
    for row in rows.values():
        row.points = (
            row.won * points[WIN]
            + row.drawn * points[DRAW]
            + row.lost * points[LOSS]
            + row.adjustment
        )
        by_group[row.group].append(row)

    rules = list(competition.tiebreak_rules or [])
    ranked = []
    for group in sorted(by_group):
        ordered = rank(by_group[group], rules, results_by_group[group], points)
        ranked += [(position, row) for position, row in enumerate(ordered, start=1)]
    return ranked


@transaction.atomic
def update_standings(edition: CompetitionSeason) -> int:
    """Recalcule et enregistre le classement ; renvoie le nombre de lignes.

    La ligne de l'édition est verrouillée : deux recalculs simultanés (deux scores saisis
    en même temps) s'exécutent l'un après l'autre au lieu de se mélanger.
    """
    edition = (
        CompetitionSeason.objects.select_for_update()
        .select_related("competition")
        .get(pk=edition.pk)
    )
    Standing.objects.filter(competition_season=edition).delete()
    if not edition.competition.has_standings:
        return 0
    standings = [
        Standing(
            competition_season=edition,
            club_id=row.club_id,
            group_name=row.group,
            position=position,
            played=row.played,
            won=row.won,
            drawn=row.drawn,
            lost=row.lost,
            goals_for=row.goals_for,
            goals_against=row.goals_against,
            goal_difference=row.goal_difference,
            points=row.points,
            form=row.form,
        )
        for position, row in compute_standings(edition)
    ]
    Standing.objects.bulk_create(standings)
    return len(standings)
