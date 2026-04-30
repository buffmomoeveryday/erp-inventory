from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from core.types import HttpRequest

from apps.users.decorators import erp_perm

from .forms import OrganizationSettingsForm
from .models import OrganizationSettings


@login_required
@erp_perm("org_settings")
def settings_hub(request: HttpRequest):
    org = OrganizationSettings.get()
    return render(
        request,
        "prefs/settings_hub.html",
        {
            "currency_code": org.currency_code,
        },
    )


@login_required
@erp_perm("org_settings")
@require_http_methods(["GET", "POST"])
def organization_settings(request: HttpRequest):
    instance = OrganizationSettings.get()
    form = OrganizationSettingsForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Currency saved.")
        return redirect("organization-settings")
    return render(
        request,
        "prefs/organization_settings.html",
        {"form": form},
    )
