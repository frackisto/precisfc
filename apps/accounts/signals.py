from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from .models import Profile, User
from .roles import should_be_staff


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, raw=False, **kwargs):
    """Chaque compte a un profil, créé avec lui (inscription, administration, commande)."""
    if created and not raw:
        Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def sync_staff_status_on_save(sender, instance, raw=False, **kwargs):
    if not raw:
        _sync_staff_status(instance)


@receiver(m2m_changed, sender=User.groups.through)
def sync_staff_status_on_roles_change(sender, instance, action, reverse, **kwargs):
    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    users = [instance] if not reverse else list(instance.user_set.all())
    for user in users:
        user.__dict__.pop("_role_keys", None)
        _sync_staff_status(user)


def _sync_staff_status(user):
    """L'accès à l'administration découle des rôles : on ne le coche jamais à la main."""
    expected = should_be_staff(user)
    if user.is_staff != expected:
        user.is_staff = expected
        User.objects.filter(pk=user.pk).update(is_staff=expected)
