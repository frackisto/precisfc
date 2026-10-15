from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """Gestionnaire d'utilisateurs identifiés par leur adresse e-mail."""

    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email):
        # L'adresse entière est mise en minuscules : une seule écriture par compte.
        return super().normalize_email(email or "").strip().lower()

    def get_by_natural_key(self, username):
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": username})

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("L'adresse e-mail est obligatoire.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["is_staff"] is not True:
            raise ValueError("Un super administrateur doit avoir is_staff=True.")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("Un super administrateur doit avoir is_superuser=True.")
        return self._create_user(email, password, **extra_fields)
