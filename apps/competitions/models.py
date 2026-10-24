from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django_countries.fields import CountryField

from apps.core.fields import ImageField
from apps.core.models import SluggedModel, TimeStampedModel


class Season(SluggedModel):
    name = models.CharField("nom", max_length=20, unique=True, help_text="Ex. 2026-2027.")
    start_date = models.DateField("début")
    end_date = models.DateField("fin")
    is_current = models.BooleanField("saison en cours", default=False)

    class Meta:
        verbose_name = "saison"
        verbose_name_plural = "saisons"
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gt=models.F("start_date")),
                name="competitions_season_ends_after_start",
                violation_error_message="La fin de saison doit suivre son début.",
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Une seule saison en cours (MariaDB n'a pas d'index unique partiel).
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.is_current:
                Season.objects.exclude(pk=self.pk).filter(is_current=True).update(is_current=False)

    @classmethod
    def current(cls):
        return cls.objects.filter(is_current=True).first()


class Club(SluggedModel):
    """Club (le nôtre ou un adversaire) apparaissant dans les matchs et classements."""

    name = models.CharField("nom", max_length=150)
    short_name = models.CharField("nom court", max_length=30, blank=True)
    logo = ImageField("logo", upload_to="clubs/", blank=True)
    city = models.CharField("ville", max_length=100, blank=True)
    country = CountryField("pays", default="CI")
    is_own_club = models.BooleanField("notre club", default=False)

    class Meta:
        verbose_name = "club"
        verbose_name_plural = "clubs"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.is_own_club:
                Club.objects.exclude(pk=self.pk).filter(is_own_club=True).update(is_own_club=False)


class TiebreakRule(models.TextChoices):
    """Critères de départage, appliqués dans l'ordre choisi après les points."""

    GOAL_DIFFERENCE = "goal_difference", "Différence de buts générale"
    GOALS_FOR = "goals_for", "Buts marqués"
    WINS = "wins", "Nombre de victoires"
    HEAD_TO_HEAD_POINTS = "head_to_head_points", "Points en confrontations directes"
    HEAD_TO_HEAD_GOAL_DIFFERENCE = (
        "head_to_head_goal_difference",
        "Différence de buts en confrontations directes",
    )
    HEAD_TO_HEAD_GOALS_FOR = "head_to_head_goals_for", "Buts marqués en confrontations directes"
    AWAY_GOALS_FOR = "away_goals_for", "Buts marqués à l'extérieur"


def default_tiebreak_rules():
    rules = [
        TiebreakRule.GOAL_DIFFERENCE,
        TiebreakRule.GOALS_FOR,
        TiebreakRule.HEAD_TO_HEAD_POINTS,
        TiebreakRule.HEAD_TO_HEAD_GOAL_DIFFERENCE,
    ]
    return [rule.value for rule in rules]


class Competition(SluggedModel):
    class Kind(models.TextChoices):
        LEAGUE = "LEAGUE", "Championnat"
        CUP = "CUP", "Coupe"
        CONTINENTAL = "CONTINENTAL", "Compétition continentale"
        INTERNATIONAL = "INTERNATIONAL", "Compétition internationale"
        FRIENDLY = "FRIENDLY", "Match amical"

    name = models.CharField("nom", max_length=150)
    kind = models.CharField("type", max_length=15, choices=Kind.choices)
    logo = ImageField("logo", upload_to="competitions/", blank=True)
    country = CountryField("pays", blank=True)
    points_win = models.PositiveSmallIntegerField("points pour une victoire", default=3)
    points_draw = models.PositiveSmallIntegerField("points pour un nul", default=1)
    points_loss = models.PositiveSmallIntegerField("points pour une défaite", default=0)
    tiebreak_rules = models.JSONField(
        "critères de départage",
        default=default_tiebreak_rules,
        blank=True,
        help_text="Liste ordonnée, appliquée après les points.",
    )
    has_standings = models.BooleanField("avec classement", default=True)

    class Meta:
        verbose_name = "compétition"
        verbose_name_plural = "compétitions"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(points_win__gt=models.F("points_draw"))
                & models.Q(points_draw__gte=models.F("points_loss")),
                name="competitions_competition_points_order",
                violation_error_message=(
                    "Une victoire doit rapporter plus qu'un nul, et un nul au moins autant "
                    "qu'une défaite."
                ),
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        rules = self.tiebreak_rules
        if not isinstance(rules, list) or not all(isinstance(rule, str) for rule in rules):
            raise ValidationError({"tiebreak_rules": "Indiquer une liste de critères."})
        unknown = sorted(set(rules) - set(TiebreakRule.values))
        if unknown:
            raise ValidationError(
                {"tiebreak_rules": f"Critère(s) inconnu(s) : {', '.join(unknown)}."}
            )
        if len(set(rules)) != len(rules):
            raise ValidationError({"tiebreak_rules": "Un critère ne peut figurer qu'une fois."})


class CompetitionSeason(TimeStampedModel):
    """Édition d'une compétition pour une saison, disputée par l'une de nos équipes."""

    competition = models.ForeignKey(
        Competition, verbose_name="compétition", on_delete=models.PROTECT, related_name="editions"
    )
    season = models.ForeignKey(
        Season, verbose_name="saison", on_delete=models.PROTECT, related_name="editions"
    )
    team = models.ForeignKey(
        "teams.Team",
        verbose_name="équipe engagée",
        on_delete=models.PROTECT,
        related_name="editions",
    )
    clubs = models.ManyToManyField(
        Club, verbose_name="participants", through="Participation", related_name="editions"
    )

    class Meta:
        verbose_name = "édition de compétition"
        verbose_name_plural = "éditions de compétitions"
        ordering = ["-season__start_date", "competition__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["competition", "season", "team"],
                name="competitions_edition_unique",
                violation_error_message="Cette équipe est déjà engagée dans cette édition.",
            ),
        ]

    def __str__(self):
        return f"{self.competition} {self.season} — {self.team}"

    def get_absolute_url(self):
        return reverse("competitions:detail", args=[self.competition.slug, self.season.slug])


class Participation(TimeStampedModel):
    competition_season = models.ForeignKey(
        CompetitionSeason,
        verbose_name="édition",
        on_delete=models.CASCADE,
        related_name="participations",
    )
    club = models.ForeignKey(
        Club, verbose_name="club", on_delete=models.PROTECT, related_name="participations"
    )
    group_name = models.CharField("groupe / poule", max_length=30, blank=True)
    points_adjustment = models.SmallIntegerField(
        "ajustement de points", default=0, help_text="Ex. -3 pour une pénalité."
    )
    adjustment_reason = models.CharField("motif de l'ajustement", max_length=255, blank=True)

    class Meta:
        verbose_name = "participant"
        verbose_name_plural = "participants"
        ordering = ["group_name", "club__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["competition_season", "club"],
                name="competitions_participation_unique",
                violation_error_message="Ce club participe déjà à cette édition.",
            ),
            models.CheckConstraint(
                condition=models.Q(points_adjustment=0) | ~models.Q(adjustment_reason=""),
                name="competitions_participation_adjustment_has_reason",
                violation_error_message="Un ajustement de points doit être motivé.",
            ),
        ]

    def __str__(self):
        return f"{self.club} — {self.competition_season}"


class Standing(TimeStampedModel):
    """Ligne de classement, recalculée par le service de classement (étape 8)."""

    competition_season = models.ForeignKey(
        CompetitionSeason,
        verbose_name="édition",
        on_delete=models.CASCADE,
        related_name="standings",
    )
    club = models.ForeignKey(
        Club, verbose_name="club", on_delete=models.CASCADE, related_name="standings"
    )
    group_name = models.CharField("groupe / poule", max_length=30, blank=True)
    position = models.PositiveSmallIntegerField("rang")
    played = models.PositiveSmallIntegerField("joués", default=0)
    won = models.PositiveSmallIntegerField("gagnés", default=0)
    drawn = models.PositiveSmallIntegerField("nuls", default=0)
    lost = models.PositiveSmallIntegerField("perdus", default=0)
    goals_for = models.PositiveSmallIntegerField("buts pour", default=0)
    goals_against = models.PositiveSmallIntegerField("buts contre", default=0)
    goal_difference = models.SmallIntegerField("différence", default=0)
    # Signé : une pénalité peut rendre le total négatif.
    points = models.SmallIntegerField("points", default=0)
    form = models.CharField("forme", max_length=5, blank=True, help_text="Ex. VVNDV.")

    class Meta:
        verbose_name = "ligne de classement"
        verbose_name_plural = "classements"
        ordering = ["competition_season", "group_name", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["competition_season", "club"], name="competitions_standing_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(played=models.F("won") + models.F("drawn") + models.F("lost")),
                name="competitions_standing_played_total",
            ),
        ]

    def __str__(self):
        return f"{self.position}. {self.club}"


class PlayerSeasonStat(TimeStampedModel):
    """Statistiques d'un joueur dans une édition, recalculées après chaque match."""

    player = models.ForeignKey(
        "teams.Player", verbose_name="joueur", on_delete=models.CASCADE, related_name="season_stats"
    )
    # Copie de competition_season.season, pour filtrer par saison sans jointure.
    season = models.ForeignKey(
        Season,
        verbose_name="saison",
        on_delete=models.CASCADE,
        related_name="player_stats",
        editable=False,
    )
    competition_season = models.ForeignKey(
        CompetitionSeason,
        verbose_name="édition",
        on_delete=models.CASCADE,
        related_name="player_stats",
    )
    appearances = models.PositiveSmallIntegerField("matchs joués", default=0)
    starts = models.PositiveSmallIntegerField("titularisations", default=0)
    minutes = models.PositiveIntegerField("minutes jouées", default=0)
    goals = models.PositiveSmallIntegerField("buts", default=0)
    assists = models.PositiveSmallIntegerField("passes décisives", default=0)
    yellow_cards = models.PositiveSmallIntegerField("cartons jaunes", default=0)
    red_cards = models.PositiveSmallIntegerField("cartons rouges", default=0)
    clean_sheets = models.PositiveSmallIntegerField("matchs sans encaisser", default=0)

    class Meta:
        verbose_name = "statistique de joueur"
        verbose_name_plural = "statistiques de joueurs"
        ordering = ["-goals", "-assists"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "competition_season"], name="competitions_playerstat_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(starts__lte=models.F("appearances")),
                name="competitions_playerstat_starts_le_appearances",
            ),
        ]

    def __str__(self):
        return f"{self.player} — {self.competition_season}"

    def save(self, *args, **kwargs):
        self.season_id = self.competition_season.season_id
        super().save(*args, **kwargs)
