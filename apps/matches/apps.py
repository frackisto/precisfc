from django.apps import AppConfig


class MatchesConfig(AppConfig):
    name = "apps.matches"
    label = "matches"
    verbose_name = "Matchs"

    def ready(self):
        from . import signals  # noqa: F401  (recalcul des classements)
