# Comptes créés avant l'étape 5 (ex. super administrateur) : le profil, désormais créé
# automatiquement à l'inscription, est ajouté à ceux qui n'en ont pas.

from django.db import migrations


def create_missing_profiles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Profile = apps.get_model("accounts", "Profile")
    Profile.objects.bulk_create(
        [Profile(user=user) for user in User.objects.filter(profile__isnull=True)]
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_profile_address"),
    ]

    operations = [
        migrations.RunPython(create_missing_profiles, migrations.RunPython.noop),
    ]
