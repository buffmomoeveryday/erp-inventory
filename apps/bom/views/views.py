from decimal import Decimal, InvalidOperation
from itertools import zip_longest

from django.contrib import messages
from django.contrib.auth.decorators import login_required

from apps.users.decorators import erp_perm
from django.db import IntegrityError, transaction
from django.db.models import Count, DecimalField, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from apps.warehouse.models import Warehouse
from apps.warehouse.services import (
    quantity_for_item_at_warehouse,
    total_quantity_for_item,
)
from django.views.decorators.http import require_http_methods

from core.types import HttpRequest

from apps.bom.models import BillOfMaterials, Item, ItemPackaging, UnitOfMeasure


def _component_context():
    return {
        "components_raw": Item.objects.filter(category="RAW")
        .select_related("uom")
        .order_by("sku"),
        "components_sub": Item.objects.filter(category="SUB")
        .select_related("uom")
        .order_by("sku"),
        "components_fin": Item.objects.filter(category="FIN")
        .select_related("uom")
        .order_by("sku"),
        "uoms": UnitOfMeasure.objects.select_related("category").order_by(
            "category__name", "name"
        ),
        "packagings": ItemPackaging.objects.filter(active=True)
        .select_related("item", "item__uom")
        .order_by("item__sku", "code"),
    }


def _parse_bom_rows(request, product: Item):
    component_ids = request.POST.getlist("component_id[]")
    qtys = request.POST.getlist("qty[]")
    uom_ids = request.POST.getlist("uom_id[]")
    packaging_ids = request.POST.getlist("packaging_id[]")
    scraps = request.POST.getlist("scrap[]")
    rows = []
    seen = set()

    for cid, qty_s, uom_id, packaging_id, scrap_s in zip_longest(
        component_ids, qtys, uom_ids, packaging_ids, scraps, fillvalue=""
    ):
        cid = (cid or "").strip()
        qty_s = (qty_s or "").strip()
        if not cid and not qty_s:
            continue
        if cid and not qty_s:
            raise ValueError(
                "Enter a quantity for every selected material or sub-assembly."
            )
        if qty_s and not cid:
            raise ValueError("Select a material or sub-assembly for each quantity.")
        try:
            cid_int = int(cid)
        except ValueError as exc:
            raise ValueError("Invalid item selection.") from exc
        if cid_int == product.pk:
            raise ValueError("The output product cannot be its own input.")
        if cid_int in seen:
            raise ValueError("Each item can only appear once on the BOM.")
        seen.add(cid_int)
        try:
            qty = Decimal(qty_s)
        except InvalidOperation as exc:
            raise ValueError("Invalid quantity.") from exc
        if qty <= 0:
            raise ValueError("Quantities must be greater than zero.")
        try:
            uom_int = int(uom_id)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid unit of measure.") from exc
        packaging_int = None
        packaging_id = (packaging_id or "").strip()
        if packaging_id:
            try:
                packaging_int = int(packaging_id)
            except ValueError as exc:
                raise ValueError("Invalid packaging selection.") from exc
        try:
            scrap = Decimal((scrap_s or "0").strip() or "0")
        except InvalidOperation as exc:
            raise ValueError("Invalid scrap percentage.") from exc
        if scrap < 0:
            raise ValueError("Scrap cannot be negative.")
        rows.append(
            {
                "component_id": cid_int,
                "quantity_required": qty,
                "uom_id": uom_int,
                "packaging_id": packaging_int,
                "scrap_factor": scrap,
            }
        )
    if not rows:
        raise ValueError("Add at least one input line to the BOM.")
    return rows


def _save_bom_lines(product: Item, rows: list[dict]) -> None:
    instances = []
    for row in rows:
        b = BillOfMaterials(
            product=product,
            component_id=row["component_id"],
            uom_id=row["uom_id"],
            packaging_id=row["packaging_id"],
            quantity_required=row["quantity_required"],
            scrap_factor=row["scrap_factor"],
        )
        b.full_clean()
        instances.append(b)
    BillOfMaterials.objects.bulk_create(instances)


@login_required
@erp_perm("view_bom")
def bom_dashboard(request):
    total_inventory_value = (
        Item.objects.aggregate(
            total=Sum(
                F("current_stock") * F("standard_cost"), output_field=DecimalField()
            )
        )["total"]
        or 0
    )

    low_stock_items = (
        Item.objects.filter(current_stock__lt=F("reorder_level"))
        .select_related("uom")
        .order_by("current_stock")
    )

    finished_goods = (
        Item.objects.filter(category="FIN")
        .annotate(num_components=Count("bom_parents"))
        .filter(num_components__gt=0)
        .order_by("-num_components")[:5]
    )

    most_used_raw = (
        Item.objects.filter(category="RAW")
        .annotate(usage_count=Count("bom_components"))
        .filter(usage_count__gt=0)
        .order_by("-usage_count")[:5]
    )

    context = {
        "total_value": total_inventory_value,
        "low_stock_count": low_stock_items.count(),
        "low_stock_items": low_stock_items[:10],
        "finished_goods": finished_goods,
        "most_used_raw": most_used_raw,
    }
    return render(request, "bom/dashboard.html", context)


@login_required
@erp_perm("view_bom")
def bom_detail_dashboard(request: HttpRequest, product_id: int):
    product = get_object_or_404(Item, pk=product_id)
    target_qty = Decimal(request.GET.get("qty", 1))
    warehouse = None
    if request.GET.get("warehouse"):
        warehouse = get_object_or_404(Warehouse, pk=int(request.GET["warehouse"]))

    bom_items = BillOfMaterials.objects.filter(product=product).select_related(
        "component",
        "component__uom",
        "uom",
        "packaging",
    )

    dashboard_data = []
    labels = []
    values = []

    for entry in bom_items:
        total_needed = entry.get_required_with_waste(target_qty)
        if warehouse:
            on_hand = quantity_for_item_at_warehouse(entry.component, warehouse)
        else:
            on_hand = total_quantity_for_item(entry.component)

        dashboard_data.append(
            {
                "component": entry.component.name,
                "sku": entry.component.sku,
                "qty_per": entry.quantity_required,
                "uom": (
                    f"{entry.packaging.code} (pkg)"
                    if entry.packaging_id
                    else entry.uom.abbreviation
                ),
                "scrap": entry.scrap_factor,
                "total_needed": total_needed,
                "stock_uom": entry.component.uom.abbreviation,
                "current_stock": on_hand,
                "shortage": max(Decimal("0"), total_needed - on_hand),
            }
        )

        labels.append(entry.component.name)
        values.append(float(total_needed))

    context = {
        "product": product,
        "target_qty": target_qty,
        "dashboard_data": dashboard_data,
        "labels": labels,
        "values": values,
        "warehouses": Warehouse.objects.filter(is_active=True).order_by("code"),
        "selected_warehouse": warehouse,
    }
    return render(request, "bom/bom_detail_dashboard.html", context)


@login_required
@erp_perm("view_bom")
def inventory_dashboard(request):
    items = Item.objects.select_related("uom").order_by("sku")
    q = (request.GET.get("q") or "").strip()
    category = (request.GET.get("category") or "").strip().upper()
    stock = (request.GET.get("stock") or "").strip().lower()

    if q:
        items = items.filter(Q(sku__icontains=q) | Q(name__icontains=q))
    if category in ("RAW", "SUB", "FIN"):
        items = items.filter(category=category)
    if stock == "low":
        items = items.filter(current_stock__lt=F("reorder_level"))
    elif stock == "ok":
        items = items.filter(current_stock__gte=F("reorder_level"))

    all_items = Item.objects.all()
    stats = {
        "total_items": all_items.count(),
        "below_reorder": all_items.filter(current_stock__lt=F("reorder_level")).count(),
        "at_or_above_reorder": all_items.filter(
            current_stock__gte=F("reorder_level")
        ).count(),
        "total_value": all_items.aggregate(
            total=Sum(
                F("current_stock") * F("standard_cost"),
                output_field=DecimalField(),
            )
        )["total"]
        or 0,
        "count_raw": all_items.filter(category="RAW").count(),
        "count_sub": all_items.filter(category="SUB").count(),
        "count_fin": all_items.filter(category="FIN").count(),
    }
    has_filters = bool(
        q or (category in ("RAW", "SUB", "FIN")) or stock in ("low", "ok")
    )

    return render(
        request,
        "bom/inventory_dashboard.html",
        {
            "items": items,
            "filter_q": q,
            "filter_category": category if category in ("RAW", "SUB", "FIN") else "",
            "filter_stock": stock if stock in ("low", "ok") else "",
            "stats": stats,
            "filtered_count": items.count(),
            "has_filters": has_filters,
        },
    )


@login_required
@erp_perm("change_bom")
@require_http_methods(["GET", "POST"])
def create_bom(request):
    products = Item.objects.filter(category__in=["FIN", "SUB"]).order_by("sku")
    ctx = {
        "products": products,
        "mode": "create",
        "bom_lines": [],
        "selected_product_id": None,
        **_component_context(),
    }

    if request.method == "POST":
        try:
            pid = int(request.POST.get("product", ""))
        except ValueError:
            messages.error(request, "Select a valid output product.")
            return render(request, "bom/create_bom.html", ctx, status=400)
        product = get_object_or_404(Item, pk=pid, category__in=["FIN", "SUB"])
        if BillOfMaterials.objects.filter(product=product).exists():
            messages.error(
                request,
                "This product already has a BOM. Use Edit BOM to change it.",
            )
            ctx["selected_product_id"] = pid
            return render(request, "bom/create_bom.html", ctx, status=400)
        try:
            rows = _parse_bom_rows(request, product)
        except ValueError as e:
            messages.error(request, str(e))
            ctx["selected_product_id"] = pid
            return render(request, "bom/create_bom.html", ctx, status=400)
        try:
            with transaction.atomic():
                _save_bom_lines(product, rows)
        except IntegrityError:
            messages.error(
                request,
                "Could not save: duplicate component or data conflict. Refresh and try again.",
            )
            ctx["selected_product_id"] = pid
            return render(request, "bom/create_bom.html", ctx, status=400)
        messages.success(
            request,
            f"BOM saved for {product.sku}. You can review requirements or edit lines anytime.",
        )
        return redirect("bom-detail-dashboard", product_id=product.pk)

    return render(request, "bom/create_bom.html", ctx)


@login_required
@erp_perm("change_bom")
@require_http_methods(["GET", "POST"])
def edit_bom(request, product_id: int):
    product = get_object_or_404(Item, pk=product_id, category__in=["FIN", "SUB"])
    bom_lines = list(
        BillOfMaterials.objects.filter(product=product)
        .select_related("component", "uom", "packaging")
        .order_by("component__sku")
    )
    products = Item.objects.filter(category__in=["FIN", "SUB"]).order_by("sku")
    ctx = {
        "products": products,
        "product": product,
        "mode": "edit",
        "bom_lines": bom_lines,
        **_component_context(),
    }

    if request.method == "POST":
        try:
            pid = int(request.POST.get("product", ""))
        except ValueError:
            messages.error(request, "Select a valid output product.")
            return render(request, "bom/edit_bom.html", ctx, status=400)
        if pid != product.pk:
            messages.error(
                request, "You cannot change the output product when editing."
            )
            return render(request, "bom/edit_bom.html", ctx, status=400)
        try:
            rows = _parse_bom_rows(request, product)
        except ValueError as e:
            messages.error(request, str(e))
            return render(request, "bom/edit_bom.html", ctx, status=400)
        try:
            with transaction.atomic():
                BillOfMaterials.objects.filter(product=product).delete()
                _save_bom_lines(product, rows)
        except IntegrityError:
            messages.error(
                request,
                "Could not save: duplicate component or data conflict. Refresh and try again.",
            )
            return render(request, "bom/edit_bom.html", ctx, status=400)
        messages.success(request, f"BOM updated for {product.sku}.")
        return redirect("bom-detail-dashboard", product_id=product.pk)

    return render(request, "bom/edit_bom.html", ctx)


@login_required
@erp_perm("change_bom")
def add_bom_row(request):
    return render(
        request,
        "bom/partials/bom_row.html",
        _component_context(),
    )
