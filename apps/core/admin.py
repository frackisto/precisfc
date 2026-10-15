from django.contrib import admin

from .models import ScheduledJobRun


@admin.register(ScheduledJobRun)
class ScheduledJobRunAdmin(admin.ModelAdmin):
    list_display = ("name", "last_status", "last_started_at", "last_finished_at", "locked_until")
    list_filter = ("last_status",)
    readonly_fields = [field.name for field in ScheduledJobRun._meta.fields]

    def has_add_permission(self, request):
        return False
