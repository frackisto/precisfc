from django.db import models


class TimeStampedModel(models.Model):
    """Base commune : dates de création et de dernière modification."""

    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        abstract = True


class ScheduledJobRun(models.Model):
    """État d'une tâche périodique exécutée par le cron (voir core/scheduling.py)."""

    class Status(models.TextChoices):
        NEVER = "", "Jamais exécutée"
        SUCCESS = "success", "Réussie"
        FAILED = "failed", "Échouée"

    name = models.CharField("tâche", max_length=150, unique=True)
    last_started_at = models.DateTimeField("dernier démarrage", null=True, blank=True)
    last_finished_at = models.DateTimeField("dernière fin", null=True, blank=True)
    last_status = models.CharField(
        "dernier statut", max_length=10, choices=Status.choices, blank=True, default=Status.NEVER
    )
    last_error = models.TextField("dernière erreur", blank=True)
    # Verrou à durée limitée : empêche deux exécutions simultanées de la même tâche.
    locked_until = models.DateTimeField("verrouillée jusqu'à", null=True, blank=True)

    class Meta:
        verbose_name = "exécution de tâche planifiée"
        verbose_name_plural = "exécutions de tâches planifiées"
        ordering = ["name"]

    def __str__(self):
        return self.name
