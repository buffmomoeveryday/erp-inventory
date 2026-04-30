from django.contrib import admin

from .models import OrganizationSettings


@admin.register(OrganizationSettings)
class OrganizationSettingsAdmin(admin.ModelAdmin):
    list_display = ["id", "currency_code"]

    def has_add_permission(self, request):
        return not OrganizationSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
