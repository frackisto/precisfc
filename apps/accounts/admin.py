from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import AdminUserCreationForm, UserChangeForm
from .models import Address, Profile, User
from .roles import SUPERADMIN_LABEL


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = AdminUserCreationForm
    form = UserChangeForm

    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "roles", "is_active", "date_joined")
    list_filter = ("groups", "is_staff", "is_superuser", "is_active")
    search_fields = ("email", "first_name", "last_name")
    inlines = [ProfileInline, AddressInline]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informations personnelles", {"fields": ("first_name", "last_name")}),
        (
            "Rôles",
            {
                "description": (
                    "Les droits se donnent uniquement par les rôles. L'accès à "
                    "l'administration (« statut équipe ») en découle automatiquement."
                ),
                "fields": ("is_active", "is_superuser", "groups", "is_staff"),
            },
        ),
        ("Dates importantes", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "usable_password", "password1", "password2"),
            },
        ),
    )

    readonly_fields = ("is_staff", "last_login", "date_joined")
    filter_horizontal = ("groups",)

    @admin.display(description="rôles")
    def roles(self, obj):
        names = [SUPERADMIN_LABEL] if obj.is_superuser else []
        names += [group.name for group in obj.groups.all()]
        return ", ".join(names) or "Supporter"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("groups")

    def get_inlines(self, request, obj):
        # Pas de profil ni d'adresse sur le formulaire de création.
        return self.inlines if obj else []
