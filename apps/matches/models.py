from auditlog.registry import auditlog
from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.fields import URLField
from apps.core.models import SluggedModel, TimeStampedModel


class Side(models.TextChoices):
    HOME = "HOME", "Domicile"
    AWAY = "AWAY", "Extérieur"


class MatchQuerySet(models.QuerySet):
    def public(self):
        return self.filter(is_published=True).select_related(
            "home_club",
            "away_club",
            "competition_season__competition",
            "competition_season__season",
            "venue",
        )

    def upcoming(self, now=None):
        now = now or timezone.now()
        return (
            self.public()
            .filter(kickoff_at__gte=now, status__in=["SCHEDULED", "LIVE", "POSTPONED"])
            .order_by("kickoff_at")
        )

    def results(self):
        return self.public().filter(status="FINISHED").order_by("-kickoff_at")

    def own_club(self):
        """Matchs de notre club (les autres servent seulement au calcul des classements)."""
        return self.filter(
            models.Q(home_club__is_own_club=True) | models.Q(away_club__is_own_club=True)
        )


class Match(SluggedModel):
    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Programmé"
        LIVE = "LIVE", "En cours"
        FINISHED = "FINISHED", "Terminé"
        POSTPONED = "POSTPONED", "Reporté"
        CANCELLED = "CANCELLED", "Annulé"

    slug_source = "slug_label"

    competition_season = models.ForeignKey(
        "competitions.CompetitionSeason",
        verbose_name="édition",
        on_delete=models.PROTECT,
        related_name="matches",
    )
    matchday = models.PositiveSmallIntegerField("journée", null=True, blank=True)
    round_label = models.CharField(
        "tour", max_length=50, blank=True, help_text="Ex. huitièmes de finale."
    )
    home_club = models.ForeignKey(
        "competitions.Club",
        verbose_name="club à domicile",
        on_delete=models.PROTECT,
        related_name="home_matches",
    )
    away_club = models.ForeignKey(
        "competitions.Club",
        verbose_name="club à l'extérieur",
        on_delete=models.PROTECT,
        related_name="away_matches",
    )
    kickoff_at = models.DateTimeField("coup d'envoi")
    original_kickoff_at = models.DateTimeField("horaire initial", null=True, blank=True)
    venue = models.ForeignKey(
        "core.Facility",
        verbose_name="lieu",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matches",
    )
    venue_name = models.CharField(
        "lieu (autre)", max_length=150, blank=True, help_text="Si le stade n'est pas enregistré."
    )
    status = models.CharField(
        "statut", max_length=10, choices=Status.choices, default=Status.SCHEDULED
    )
    home_score = models.PositiveSmallIntegerField("buts domicile", null=True, blank=True)
    away_score = models.PositiveSmallIntegerField("buts extérieur", null=True, blank=True)
    home_penalties = models.PositiveSmallIntegerField("tirs au but domicile", null=True, blank=True)
    away_penalties = models.PositiveSmallIntegerField(
        "tirs au but extérieur", null=True, blank=True
    )
    referee = models.CharField("arbitre central", max_length=150, blank=True)
    assistant_referees = models.CharField("arbitres assistants", max_length=255, blank=True)
    fourth_official = models.CharField("quatrième arbitre", max_length=150, blank=True)
    attendance = models.PositiveIntegerField("affluence", null=True, blank=True)
    report = models.TextField("compte rendu", blank=True)
    highlights_video = URLField("vidéo des temps forts", blank=True)
    is_published = models.BooleanField("publié", default=True)

    objects = MatchQuerySet.as_manager()

    class Meta:
        verbose_name = "match"
        verbose_name_plural = "matchs"
        ordering = ["-kickoff_at"]
        indexes = [models.Index(fields=["status", "kickoff_at"])]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(home_club=models.F("away_club")),
                name="matches_match_distinct_clubs",
                violation_error_message="Un club ne peut pas jouer contre lui-même.",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="FINISHED")
                | models.Q(home_score__isnull=False, away_score__isnull=False),
                name="matches_match_finished_has_score",
                violation_error_message="Un match terminé doit avoir un score.",
            ),
            models.CheckConstraint(
                condition=models.Q(home_penalties__isnull=True, away_penalties__isnull=True)
                | models.Q(home_penalties__isnull=False, away_penalties__isnull=False),
                name="matches_match_penalties_both_or_none",
                violation_error_message="Indiquer les tirs au but des deux équipes.",
            ),
        ]

    def __str__(self):
        return f"{self.home_club} - {self.away_club} ({self.kickoff_at:%d/%m/%Y})"

    @property
    def slug_label(self):
        kickoff = timezone.localtime(self.kickoff_at)
        return f"{self.home_club.name} {self.away_club.name} {kickoff:%Y-%m-%d}"

    def get_absolute_url(self):
        return reverse("matches:detail", args=[self.slug])

    @property
    def is_rescheduled(self):
        return self.original_kickoff_at is not None and self.original_kickoff_at != self.kickoff_at

    def save(self, *args, **kwargs):
        """Garde l'historique des changements d'horaire (reports).

        L'administration renseigne ``changed_by`` et, si elle le souhaite,
        ``schedule_change_reason`` avant l'enregistrement.
        """
        previous = None
        if self.pk:
            previous = (
                Match.objects.filter(pk=self.pk)
                .values("kickoff_at", "competition_season_id")
                .first()
            )
        rescheduled = previous is not None and previous["kickoff_at"] != self.kickoff_at
        if rescheduled and self.original_kickoff_at is None:
            self.original_kickoff_at = previous["kickoff_at"]
        # Lu par le signal de recalcul : un match changé d'édition recalcule les deux.
        self._previous_edition_id = previous["competition_season_id"] if previous else None
        super().save(*args, **kwargs)
        if rescheduled:
            MatchScheduleChange.objects.create(
                match=self,
                old_kickoff_at=previous["kickoff_at"],
                new_kickoff_at=self.kickoff_at,
                reason=getattr(self, "schedule_change_reason", "") or "Changement d'horaire",
                changed_by=getattr(self, "changed_by", None),
            )
        # Le motif ne vaut que pour ce changement : pas pour un report ultérieur.
        self.__dict__.pop("schedule_change_reason", None)


class MatchScheduleChange(TimeStampedModel):
    """Historique des changements d'horaire (reports)."""

    match = models.ForeignKey(
        Match, verbose_name="match", on_delete=models.CASCADE, related_name="schedule_changes"
    )
    old_kickoff_at = models.DateTimeField("ancien horaire")
    new_kickoff_at = models.DateTimeField("nouvel horaire", null=True, blank=True)
    reason = models.CharField("motif", max_length=255)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="modifié par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "changement d'horaire"
        verbose_name_plural = "changements d'horaire"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.match} : {self.old_kickoff_at:%d/%m/%Y %H:%M}"


def _player_or_name(prefix: str, name: str, message: str) -> models.CheckConstraint:
    """Contrainte : un joueur enregistré ou, pour l'adversaire, son nom en clair."""
    return models.CheckConstraint(
        condition=models.Q(**{f"{prefix}__isnull": False}) | ~models.Q(**{f"{prefix}_name": ""}),
        name=name,
        violation_error_message=message,
    )


class LineupEntry(TimeStampedModel):
    match = models.ForeignKey(
        Match, verbose_name="match", on_delete=models.CASCADE, related_name="lineup"
    )
    side = models.CharField("équipe", max_length=4, choices=Side.choices)
    player = models.ForeignKey(
        "teams.Player",
        verbose_name="joueur",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lineup_entries",
    )
    player_name = models.CharField("joueur (adversaire)", max_length=150, blank=True)
    shirt_number = models.PositiveSmallIntegerField(
        "numéro", null=True, blank=True, validators=[MaxValueValidator(99)]
    )
    position = models.CharField("poste", max_length=30, blank=True)
    is_starter = models.BooleanField("titulaire", default=True)
    is_captain = models.BooleanField("capitaine", default=False)
    order = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "joueur de la composition"
        verbose_name_plural = "compositions"
        ordering = ["side", "-is_starter", "order"]
        constraints = [
            _player_or_name(
                "player", "matches_lineup_player_or_name", "Choisir un joueur ou saisir son nom."
            ),
            models.UniqueConstraint(
                fields=["match", "player"],
                name="matches_lineup_unique_player",
                violation_error_message="Ce joueur figure déjà dans la composition.",
            ),
        ]

    def __str__(self):
        return str(self.player or self.player_name)


class MatchEvent(TimeStampedModel):
    class Kind(models.TextChoices):
        GOAL = "GOAL", "But"
        PENALTY_GOAL = "PENALTY_GOAL", "But sur penalty"
        OWN_GOAL = "OWN_GOAL", "But contre son camp"
        MISSED_PENALTY = "MISSED_PENALTY", "Penalty manqué"
        YELLOW = "YELLOW", "Carton jaune"
        SECOND_YELLOW = "SECOND_YELLOW", "Second carton jaune"
        RED = "RED", "Carton rouge"
        SUBSTITUTION = "SUBSTITUTION", "Remplacement"

    match = models.ForeignKey(
        Match, verbose_name="match", on_delete=models.CASCADE, related_name="events"
    )
    side = models.CharField("équipe", max_length=4, choices=Side.choices)
    minute = models.PositiveSmallIntegerField("minute", validators=[MaxValueValidator(130)])
    added_time = models.PositiveSmallIntegerField(
        "temps additionnel", default=0, validators=[MaxValueValidator(30)]
    )
    kind = models.CharField("type", max_length=15, choices=Kind.choices)
    player = models.ForeignKey(
        "teams.Player",
        verbose_name="joueur",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="match_events",
    )
    player_name = models.CharField("joueur (adversaire)", max_length=150, blank=True)
    assist_player = models.ForeignKey(
        "teams.Player",
        verbose_name="passeur",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assists",
    )
    assist_name = models.CharField("passeur (adversaire)", max_length=150, blank=True)
    player_out = models.ForeignKey(
        "teams.Player",
        verbose_name="joueur sortant",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="substituted_events",
    )
    player_out_name = models.CharField("joueur sortant (adversaire)", max_length=150, blank=True)
    note = models.CharField("remarque", max_length=255, blank=True)

    class Meta:
        verbose_name = "événement de match"
        verbose_name_plural = "événements de match"
        ordering = ["match", "minute", "added_time", "pk"]
        constraints = [
            _player_or_name(
                "player", "matches_event_player_or_name", "Choisir un joueur ou saisir son nom."
            ),
            models.CheckConstraint(
                condition=~models.Q(kind="SUBSTITUTION")
                | models.Q(player_out__isnull=False)
                | ~models.Q(player_out_name=""),
                name="matches_event_substitution_has_player_out",
                violation_error_message="Un remplacement doit indiquer le joueur sortant.",
            ),
        ]

    def __str__(self):
        minute = f"{self.minute}+{self.added_time}" if self.added_time else str(self.minute)
        return f"{minute}' {self.get_kind_display()} — {self.player or self.player_name}"


class MatchTeamStat(TimeStampedModel):
    match = models.ForeignKey(
        Match, verbose_name="match", on_delete=models.CASCADE, related_name="team_stats"
    )
    side = models.CharField("équipe", max_length=4, choices=Side.choices)
    possession = models.PositiveSmallIntegerField(
        "possession (%)", null=True, blank=True, validators=[MaxValueValidator(100)]
    )
    shots = models.PositiveSmallIntegerField("tirs", default=0)
    shots_on_target = models.PositiveSmallIntegerField("tirs cadrés", default=0)
    corners = models.PositiveSmallIntegerField("corners", default=0)
    fouls = models.PositiveSmallIntegerField("fautes", default=0)
    offsides = models.PositiveSmallIntegerField("hors-jeu", default=0)
    saves = models.PositiveSmallIntegerField("arrêts", default=0)

    class Meta:
        verbose_name = "statistique d'équipe"
        verbose_name_plural = "statistiques d'équipe"
        ordering = ["match", "side"]
        constraints = [
            models.UniqueConstraint(fields=["match", "side"], name="matches_teamstat_unique"),
            models.CheckConstraint(
                condition=models.Q(shots_on_target__lte=models.F("shots")),
                name="matches_teamstat_on_target_le_shots",
                violation_error_message="Les tirs cadrés ne peuvent dépasser le nombre de tirs.",
            ),
            models.CheckConstraint(
                condition=models.Q(possession__isnull=True) | models.Q(possession__lte=100),
                name="matches_teamstat_possession_max_100",
            ),
        ]

    def __str__(self):
        return f"{self.match} — {self.get_side_display()}"


# Historique des modifications des matchs (scores saisis, reports) avec leur auteur.
auditlog.register(Match, exclude_fields=["updated_at"])
