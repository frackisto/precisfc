from django.contrib import admin

from .models import AcademyEvent, AgeCategory, Application, ApplicationDocument, TrainingProgram


@admin.register(AgeCategory)
class AgeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "min_birth_year", "max_birth_year", "team", "order")
    list_editable = ("order",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(TrainingProgram)
class TrainingProgramAdmin(admin.ModelAdmin):
    list_display = ("title", "age_category", "order", "is_published")
    list_filter = ("age_category", "is_published")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(AcademyEvent)
class AcademyEventAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "starts_at", "age_category", "is_published")
    list_filter = ("kind", "age_category", "is_published")
    date_hierarchy = "starts_at"
    search_fields = ("title", "location")


class ApplicationDocumentInline(admin.TabularInline):
    """Les fichiers sont privés : pas de lien de téléchargement direct. Le
    téléchargement contrôlé par rôle est ajouté à l'étape 14."""

    model = ApplicationDocument
    extra = 0
    can_delete = False
    fields = ("kind", "original_name", "size", "content_type", "created_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("reference", "last_name", "first_name", "birth_date", "age_category", "status")
    list_filter = ("status", "age_category", "gender")
    search_fields = ("reference", "last_name", "first_name", "guardian_name")
    date_hierarchy = "created_at"
    inlines = [ApplicationDocumentInline]
    readonly_fields = ("reference", "consent_given", "consent_at", "created_at")
    fieldsets = (
        (
            "Candidat",
            {
                "fields": (
                    "reference",
                    ("first_name", "last_name"),
                    ("birth_date", "gender", "nationality"),
                    ("city", "email", "phone"),
                )
            },
        ),
        (
            "Profil sportif",
            {
                "fields": (
                    "age_category",
                    ("position", "preferred_foot"),
                    "current_club",
                    "experience",
                )
            },
        ),
        (
            "Représentant légal",
            {
                "fields": (
                    ("guardian_name", "guardian_relationship"),
                    ("guardian_phone", "guardian_email"),
                )
            },
        ),
        ("Consentement", {"fields": (("consent_given", "consent_at"), "created_at")}),
        ("Suivi", {"fields": ("status", "internal_notes", "reviewed_by", "retention_until")}),
    )

    def has_add_permission(self, request):
        # Les candidatures arrivent par le formulaire public (avec consentement).
        return False
