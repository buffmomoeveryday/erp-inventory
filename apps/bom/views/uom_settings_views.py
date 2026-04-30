from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from core.types import HttpRequest

from apps.bom.forms import UOMCategoryForm, UnitOfMeasureForm
from apps.bom.models import UOMCategory, UnitOfMeasure
from apps.users.decorators import erp_perm


@login_required
@erp_perm("uom_settings")
def uom_settings_hub(request: HttpRequest):
    return render(
        request,
        "bom/settings/uom_hub.html",
        {
            "category_count": UOMCategory.objects.count(),
            "unit_count": UnitOfMeasure.objects.count(),
        },
    )


@login_required
@erp_perm("uom_settings")
def uom_category_list(request: HttpRequest):
    categories = UOMCategory.objects.prefetch_related("units").order_by("name")
    return render(
        request,
        "bom/settings/uom_category_list.html",
        {"categories": categories},
    )


@login_required
@erp_perm("uom_settings")
@require_http_methods(["GET", "POST"])
def uom_category_create(request: HttpRequest):
    form = UOMCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "UOM category saved.")
        return redirect("uom-category-list")
    return render(
        request,
        "bom/settings/uom_category_form.html",
        {"form": form, "title": "New UOM category"},
    )


@login_required
@erp_perm("uom_settings")
@require_http_methods(["GET", "POST"])
def uom_category_edit(request: HttpRequest, pk: int):
    cat = get_object_or_404(UOMCategory, pk=pk)
    form = UOMCategoryForm(request.POST or None, instance=cat)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "UOM category updated.")
        return redirect("uom-category-list")
    return render(
        request,
        "bom/settings/uom_category_form.html",
        {"form": form, "title": f"Edit {cat.name}", "category": cat},
    )


@login_required
@erp_perm("uom_settings")
def uom_list(request: HttpRequest):
    units = UnitOfMeasure.objects.select_related("category").order_by(
        "category__name", "name"
    )
    cat_id = (request.GET.get("category") or "").strip()
    if cat_id.isdigit():
        units = units.filter(category_id=int(cat_id))
    categories = UOMCategory.objects.order_by("name")
    return render(
        request,
        "bom/settings/uom_list.html",
        {
            "units": units,
            "categories": categories,
            "filter_category": cat_id if cat_id.isdigit() else "",
        },
    )


@login_required
@erp_perm("uom_settings")
@require_http_methods(["GET", "POST"])
def uom_create(request: HttpRequest):
    form = UnitOfMeasureForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Unit of measure saved.")
        return redirect("uom-list")
    return render(
        request,
        "bom/settings/uom_form.html",
        {"form": form, "title": "New unit of measure"},
    )


@login_required
@erp_perm("uom_settings")
@require_http_methods(["GET", "POST"])
def uom_edit(request: HttpRequest, pk: int):
    u = get_object_or_404(UnitOfMeasure.objects.select_related("category"), pk=pk)
    form = UnitOfMeasureForm(request.POST or None, instance=u)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Unit of measure updated.")
        return redirect("uom-list")
    return render(
        request,
        "bom/settings/uom_form.html",
        {"form": form, "title": f"Edit {u.name}", "unit": u},
    )
