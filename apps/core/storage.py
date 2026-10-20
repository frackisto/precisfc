from django.conf import settings
from django.core.files.storage import FileSystemStorage, storages


class PrivateStorage(FileSystemStorage):
    """Stockage des fichiers sensibles (candidatures, pièces jointes).

    Les fichiers sont rangés hors des dossiers publics et n'ont pas d'URL :
    ils ne peuvent être téléchargés que par une vue qui contrôle les permissions.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("location", settings.PRIVATE_MEDIA_ROOT)
        kwargs["base_url"] = None
        kwargs.setdefault("file_permissions_mode", 0o600)
        kwargs.setdefault("directory_permissions_mode", 0o700)
        super().__init__(**kwargs)

    def url(self, name):
        raise NotImplementedError(
            "Un fichier privé n'a pas d'URL publique : utiliser une vue de téléchargement "
            "qui vérifie les permissions."
        )


def private_storage():
    """Stockage privé, pour ``FileField(storage=private_storage)``.

    Un appelable plutôt qu'une instance : les migrations ne figent ni la classe ni le
    dossier, qui restent définis par le réglage ``STORAGES["private"]``.
    """
    return storages["private"]
