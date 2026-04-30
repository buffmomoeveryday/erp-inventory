from django.urls import path

from . import views

urlpatterns = [
    path("", views.settings_hub, name="settings-hub"),
    path(
        "organization/",
        views.organization_settings,
        name="organization-settings",
    ),
]
