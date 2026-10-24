from django.contrib.admin.apps import AdminConfig


class ClubAdminConfig(AdminConfig):
    """Remplace ``django.contrib.admin`` : même administration, aux couleurs du club."""

    default_site = "apps.dashboard.admin_site.ClubAdminSite"
