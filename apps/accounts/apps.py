from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Comptes et profils"

    def ready(self):
        from . import signals  # noqa: F401  (profil automatique, accès selon les rôles)
