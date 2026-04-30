from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.bom.models import BillOfMaterials
from apps.users.decorators import erp_perm
from apps.warehouse.services import (
    get_default_warehouse,
    quantity_for_item_at_warehouse,
)

from .forms import ProductionOrderForm
from .models import ProductionOrder


@login_required
@erp_perm("production_read")
def production_order_list(request):
    qs = ProductionOrder.objects.select_related(
        "product",
        "product__uom",
        "source_warehouse",
        "destination_warehouse",
        "approved_by",
    ).order_by("-created_at")
    status = (request.GET.get("status") or "").strip().upper()
    if status in ProductionOrder.Status.values:
        qs = qs.filter(status=status)
    return render(
        request,
        "production/order_list.html",
        {
            "orders": qs,
            "filter_status": status if status in ProductionOrder.Status.values else "",
            "status_choices": ProductionOrder.Status.choices,
        },
    )


@login_required
@erp_perm("production_write")
@require_http_methods(["GET", "POST"])
def production_order_create(request):
    form = ProductionOrderForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        order = form.save()
        messages.success(
            request,
            f"Production order {order.batch_number} created as draft.",
        )
        return redirect("production-order-detail", pk=order.pk)
    return render(
        request,
        "production/order_form.html",
        {"form": form},
    )


@login_required
@erp_perm("production_read")
def production_order_detail(request, pk: int):
    order = get_object_or_404(
        ProductionOrder.objects.select_related(
            "product",
            "product__uom",
            "source_warehouse",
            "destination_warehouse",
            "approved_by",
        ),
        pk=pk,
    )
    bom_qs = BillOfMaterials.objects.filter(product=order.product).select_related(
        "component",
        "component__uom",
        "uom",
    )
    wh = order.source_warehouse or get_default_warehouse()
    material_lines = []
    for bom in bom_qs:
        required = bom.get_required_with_waste(order.quantity_to_produce)
        stock = quantity_for_item_at_warehouse(bom.component, wh)
        material_lines.append(
            {
                "bom": bom,
                "required": required,
                "stock": stock,
                "short": max(Decimal("0"), required - stock),
                "ok": stock >= required,
            }
        )
    has_bom = bool(material_lines)
    return render(
        request,
        "production/order_detail.html",
        {
            "order": order,
            "material_lines": material_lines,
            "has_bom": has_bom,
            "can_start": order.can_start() if has_bom else True,
        },
    )


@login_required
@erp_perm("production_approve")
@require_http_methods(["POST"])
def production_order_approve(request, pk: int):
    order = get_object_or_404(ProductionOrder, pk=pk)
    if order.status not in (
        ProductionOrder.Status.DRAFT,
        ProductionOrder.Status.PENDING,
    ):
        messages.error(request, "Only draft or pending orders can be approved.")
    elif order.approved_at:
        messages.info(request, "This order is already approved.")
    else:
        order.approved_at = timezone.now()
        order.approved_by = request.user
        order.save(update_fields=["approved_at", "approved_by"])
        messages.success(request, f"{order.batch_number} approved.")
    return redirect("production-order-detail", pk=pk)


@login_required
@erp_perm("production_write")
@require_http_methods(["POST"])
def production_order_start(request, pk: int):
    order = get_object_or_404(ProductionOrder, pk=pk)
    try:
        order.start_production()
        messages.success(request, f"{order.batch_number} is now in progress.")
    except ValidationError as e:
        messages.error(request, e.messages[0] if e.messages else str(e))
    return redirect("production-order-detail", pk=pk)


@login_required
@erp_perm("production_write")
@require_http_methods(["POST"])
def production_order_complete(request, pk: int):
    order = get_object_or_404(ProductionOrder, pk=pk)
    try:
        order.complete_production()
        messages.success(request, f"{order.batch_number} completed. Stock updated.")
    except ValidationError as e:
        messages.error(request, e.messages[0] if e.messages else str(e))
    return redirect("production-order-detail", pk=pk)


@login_required
@erp_perm("production_write")
@require_http_methods(["POST"])
def production_order_cancel(request, pk: int):
    order = get_object_or_404(ProductionOrder, pk=pk)
    if order.status in (
        ProductionOrder.Status.COMPLETED,
        ProductionOrder.Status.CANCELLED,
    ):
        messages.error(request, "This order cannot be cancelled.")
    elif order.status == ProductionOrder.Status.IN_PROGRESS:
        messages.error(request, "Cannot cancel an in-progress order from here.")
    else:
        order.status = ProductionOrder.Status.CANCELLED
        order.save(update_fields=["status"])
        messages.success(request, f"{order.batch_number} cancelled.")
    return redirect("production-order-detail", pk=pk)
