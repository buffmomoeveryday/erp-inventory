from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.urls import include, path, reverse


_DASHBOARD_REDIRECTS = (
    ("users.view_bom", "bom-dashboard"),
    ("users.view_items", "item-list"),
    ("users.warehouse_read", "warehouse-list"),
    ("users.procurement_read", "purchase-order-list"),
    ("users.production_read", "production-order-list"),
    ("users.org_settings", "settings-hub"),
)


@login_required
def dashboard(request: HttpRequest):
    for perm, url_name in _DASHBOARD_REDIRECTS:
        if request.user.has_perm(perm):
            return redirect(reverse(url_name))
    return render(request, "users/no_access.html", status=403)


urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("bom/", include("apps.bom.urls")),
    path("warehouses/", include("apps.warehouse.urls")),
    path("procurement/", include("apps.procurement.urls")),
    path("production/", include("apps.production.urls")),
    path("admin/", admin.site.urls),
    path("users/", include("apps.users.urls")),
    path("settings/", include("apps.prefs.urls")),
    path("__reload__/", include("django_browser_reload.urls")),
]
