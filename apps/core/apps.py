from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    label = "core"
    verbose_name = "Identité du club"

    def ready(self):
        from . import checks  # noqa: F401  (enregistre les contrôles système)
