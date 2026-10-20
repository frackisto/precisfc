from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.roles import ROLES, SUPERADMIN_LABEL


def resolve_permissions(names: frozenset[str]) -> list[Permission]:
    """Permissions ``app.codename`` ; erreur si l'une n'existe pas (faute de frappe)."""
    wanted = {tuple(name.split(".", 1)) for name in names}
    found = Permission.objects.filter(
        content_type__app_label__in={app for app, _ in wanted},
        codename__in={codename for _, codename in wanted},
    ).select_related("content_type")
    by_name = {(perm.content_type.app_label, perm.codename): perm for perm in found}
    missing = sorted(f"{app}.{codename}" for app, codename in wanted - by_name.keys())
    if missing:
        raise CommandError(f"Permissions introuvables : {', '.join(missing)}")
    return [by_name[key] for key in wanted]


class Command(BaseCommand):
    help = "Crée ou met à jour les groupes des rôles du club et leurs permissions (idempotente)."

    @transaction.atomic
    def handle(self, *args, **options):
        for role in ROLES.values():
            group, created = Group.objects.get_or_create(name=role.name)
            permissions = resolve_permissions(role.all_permissions)
            group.permissions.set(permissions)
            state = "créé" if created else "à jour"
            self.stdout.write(f"{role.name} : {state} ({len(permissions)} permissions)")
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(ROLES) + 1} rôles prêts ({SUPERADMIN_LABEL} = superutilisateur Django)."
            )
        )
