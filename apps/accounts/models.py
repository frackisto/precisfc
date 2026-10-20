from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField

from apps.core.models import TimeStampedModel

from .managers import UserManager


class User(AbstractUser):
    """Compte utilisateur : la connexion se fait par adresse e-mail.

    Le téléphone et les préférences sont dans le modèle ``Profile``.
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


class Profile(TimeStampedModel):
    """Informations complémentaires d'un compte (créé avec l'utilisateur à l'étape 5)."""

    user = models.OneToOneField(
        User, verbose_name="utilisateur", on_delete=models.CASCADE, related_name="profile"
    )
    phone = PhoneNumberField("téléphone", blank=True)
    avatar = models.ImageField("photo de profil", upload_to="avatars/", blank=True)
    city = models.CharField("ville", max_length=100, blank=True)
    country = CountryField("pays", default="CI", blank=True)
    birth_date = models.DateField("date de naissance", null=True, blank=True)
    notify_news = models.BooleanField("actualités du club", default=True)
    notify_matches = models.BooleanField("rappels de match", default=True)
    notify_shop = models.BooleanField("offres de la boutique", default=False)
    notify_tickets = models.BooleanField("ouverture de la billetterie", default=True)

    class Meta:
        verbose_name = "profil"
        verbose_name_plural = "profils"

    def __str__(self):
        return f"Profil de {self.user}"


class Address(TimeStampedModel):
    """Adresse de livraison enregistrée par un supporter."""

    user = models.ForeignKey(
        User, verbose_name="utilisateur", on_delete=models.CASCADE, related_name="addresses"
    )
    label = models.CharField("libellé", max_length=50, help_text="Ex. Maison, Bureau.")
    full_name = models.CharField("nom du destinataire", max_length=150)
    phone = PhoneNumberField("téléphone")
    line1 = models.CharField("adresse", max_length=255)
    line2 = models.CharField("complément d'adresse", max_length=255, blank=True)
    commune = models.CharField("commune", max_length=100, blank=True)
    city = models.CharField("ville", max_length=100, default="Abidjan")
    country = CountryField("pays", default="CI")
    is_default = models.BooleanField("adresse par défaut", default=False)

    class Meta:
        verbose_name = "adresse"
        verbose_name_plural = "adresses"
        ordering = ["-is_default", "label"]

    def __str__(self):
        return f"{self.label} — {self.full_name}"

    def save(self, *args, **kwargs):
        # Une seule adresse par défaut par utilisateur (MariaDB n'a pas d'index partiel).
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.is_default:
                self.user.addresses.exclude(pk=self.pk).filter(is_default=True).update(
                    is_default=False
                )
