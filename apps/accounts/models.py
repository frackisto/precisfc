from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class User(AbstractUser):
    """Compte utilisateur : la connexion se fait par adresse e-mail.

    Le profil (téléphone, préférences…) est ajouté à l'étape 5.
    """

    username = None
    email = models.EmailField("adresse e-mail", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self):
        return self.get_full_name() or self.email

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)
