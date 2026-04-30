from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.users.decorators import erp_perm
from apps.warehouse.models import Warehouse

from .forms import POLineFormSet, PurchaseOrderForm, SupplierForm
from .models import PurchaseOrder, Supplier
from .services import record_goods_receipt


@login_required
@erp_perm("procurement_read")
def supplier_list(request):
    suppliers = Supplier.objects.order_by("code")
    return render(request, "procurement/supplier_list.html", {"suppliers": suppliers})


@login_required
@erp_perm("procurement_write")
@require_http_methods(["GET", "POST"])
def supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Supplier saved.")
        return redirect("supplier-list")
    return render(
        request,
        "procurement/supplier_form.html",
        {"form": form, "title": "New supplier"},
    )


@login_required
@erp_perm("procurement_read")
def purchase_order_list(request):
    qs = PurchaseOrder.objects.select_related("supplier", "approved_by").order_by(
        "-created_at"
    )
    st = (request.GET.get("status") or "").strip().upper()
    if st in PurchaseOrder.Status.values:
        qs = qs.filter(status=st)
    return render(
        request,
        "procurement/po_list.html",
        {
            "orders": qs,
            "filter_status": st if st in PurchaseOrder.Status.values else "",
            "status_choices": PurchaseOrder.Status.choices,
        },
    )


@login_required
@erp_perm("procurement_write")
@require_http_methods(["GET", "POST"])
def purchase_order_create(request):
    if request.method == "POST":
        form = PurchaseOrderForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                "procurement/po_form.html",
                {"form": form, "formset": POLineFormSet(request.POST)},
            )
        po = form.save()
        formset = POLineFormSet(request.POST, instance=po)
        if not formset.is_valid():
            po.delete()
            return render(
                request,
                "procurement/po_form.html",
                {"form": form, "formset": formset},
            )
        formset.save()
        if not po.items.exists():
            po.delete()
            messages.error(request, "Add at least one line item.")
            return render(
                request,
                "procurement/po_form.html",
                {
                    "form": PurchaseOrderForm(),
                    "formset": POLineFormSet(),
                },
            )
        messages.success(request, f"Created {po.po_number}.")
        return redirect("purchase-order-detail", pk=po.pk)
    return render(
        request,
        "procurement/po_form.html",
        {"form": PurchaseOrderForm(), "formset": POLineFormSet()},
    )


@login_required
@erp_perm("procurement_read")
def purchase_order_detail(request, pk: int):
    po = get_object_or_404(
        PurchaseOrder.objects.select_related(
            "supplier", "approved_by"
        ).prefetch_related(
            "items__item__uom",
            "receipts__receiving_warehouse",
        ),
        pk=pk,
    )
    return render(request, "procurement/po_detail.html", {"po": po})


@login_required
@erp_perm("procurement_approve")
@require_http_methods(["POST"])
def purchase_order_approve(request, pk: int):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status != PurchaseOrder.Status.DRAFT:
        messages.error(request, "Only draft purchase orders can be approved.")
    elif po.approved_at:
        messages.info(request, "This order is already approved.")
    else:
        po.approved_at = timezone.now()
        po.approved_by = request.user
        po.save(update_fields=["approved_at", "approved_by"])
        messages.success(request, f"{po.po_number} approved.")
    return redirect("purchase-order-detail", pk=pk)


@login_required
@erp_perm("procurement_approve")
@require_http_methods(["POST"])
def purchase_order_send(request, pk: int):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status != PurchaseOrder.Status.DRAFT:
        messages.error(request, "Only draft orders can be sent.")
    elif not po.approved_at:
        messages.error(
            request,
            "Approve this purchase order before sending it to the supplier.",
        )
    elif not po.items.exists():
        messages.error(request, "Add lines before sending.")
    else:
        po.status = PurchaseOrder.Status.SENT
        po.save()
        messages.success(request, f"{po.po_number} marked as sent.")
    return redirect("purchase-order-detail", pk=pk)


@login_required
@erp_perm("procurement_write")
@require_http_methods(["POST"])
def purchase_order_cancel(request, pk: int):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status != PurchaseOrder.Status.DRAFT:
        messages.error(request, "Only draft orders can be cancelled.")
    else:
        po.status = PurchaseOrder.Status.CANCELLED
        po.save()
        messages.success(request, "Order cancelled.")
    return redirect("purchase-order-detail", pk=pk)


@login_required
@erp_perm("procurement_write")
@require_http_methods(["GET", "POST"])
def purchase_order_receive(request, pk: int):
    po = get_object_or_404(
        PurchaseOrder.objects.prefetch_related("items__item__uom", "items__packaging"),
        pk=pk,
    )
    if po.status not in (PurchaseOrder.Status.SENT, PurchaseOrder.Status.PARTIAL):
        messages.error(
            request, "This order cannot receive goods in its current status."
        )
        return redirect("purchase-order-detail", pk=pk)

    warehouses = Warehouse.objects.filter(is_active=True).order_by("code")
    open_lines = [ln for ln in po.items.all() if ln.is_pending]

    if request.method == "POST":
        wh_id = request.POST.get("receiving_warehouse")
        wh = None
        if wh_id:
            wh = get_object_or_404(Warehouse, pk=int(wh_id))
        note = (request.POST.get("reference_note") or "").strip()
        quantities: dict[int, Decimal] = {}
        package_quantities: dict[int, Decimal] = {}
        for ln in open_lines:
            raw = (request.POST.get(f"qty_{ln.pk}") or "").strip()
            pkg_raw = (request.POST.get(f"pkg_qty_{ln.pk}") or "").strip()
            if not raw:
                q = Decimal("0")
            else:
                try:
                    q = Decimal(raw)
                except InvalidOperation:
                    messages.error(request, f"Invalid quantity for {ln.item.sku}.")
                    return render(
                        request,
                        "procurement/receive_form.html",
                        {"po": po, "open_lines": open_lines, "warehouses": warehouses},
                    )
            if q > 0:
                quantities[ln.pk] = q
            elif q < 0:
                messages.error(
                    request, f"Quantity cannot be negative for {ln.item.sku}."
                )
                return render(
                    request,
                    "procurement/receive_form.html",
                    {"po": po, "open_lines": open_lines, "warehouses": warehouses},
                )
            if not pkg_raw:
                pkg_q = Decimal("0")
            else:
                try:
                    pkg_q = Decimal(pkg_raw)
                except InvalidOperation:
                    messages.error(
                        request, f"Invalid package quantity for {ln.item.sku}."
                    )
                    return render(
                        request,
                        "procurement/receive_form.html",
                        {"po": po, "open_lines": open_lines, "warehouses": warehouses},
                    )
            if pkg_q > 0:
                package_quantities[ln.pk] = pkg_q
            elif pkg_q < 0:
                messages.error(
                    request, f"Package quantity cannot be negative for {ln.item.sku}."
                )
                return render(
                    request,
                    "procurement/receive_form.html",
                    {"po": po, "open_lines": open_lines, "warehouses": warehouses},
                )
        try:
            record_goods_receipt(
                po,
                wh,
                quantities,
                line_package_quantities=package_quantities,
                reference_note=note,
            )
        except ValidationError as e:
            messages.error(request, e.messages[0] if e.messages else str(e))
            return render(
                request,
                "procurement/receive_form.html",
                {"po": po, "open_lines": open_lines, "warehouses": warehouses},
            )
        messages.success(request, "Receipt recorded and stock updated.")
        return redirect("purchase-order-detail", pk=pk)

    return render(
        request,
        "procurement/receive_form.html",
        {"po": po, "open_lines": open_lines, "warehouses": warehouses},
    )
