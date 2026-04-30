from decimal import Decimal, InvalidOperation
from itertools import zip_longest

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.bom.models import Item
from apps.production.models import StockLedger
from apps.users.decorators import erp_perm
from .forms import CustomerForm, StockMoveForm, WarehouseForm, WarehouseOutForm
from .services import record_warehouse_outbound, transfer_between_warehouses
from .models import Customer, Warehouse, WarehouseStock


@login_required
@erp_perm("warehouse_read")
def customer_list(request):
    customers = Customer.objects.order_by("name")
    return render(
        request,
        "warehouse/customer_list.html",
        {"customers": customers},
    )


@login_required
@erp_perm("warehouse_write")
@require_http_methods(["GET", "POST"])
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Customer saved.")
        return redirect("customer-list")
    return render(
        request,
        "warehouse/customer_form.html",
        {"form": form, "title": "New customer"},
    )


@login_required
@erp_perm("warehouse_read")
def warehouse_list(request):
    warehouses = Warehouse.objects.order_by("code")
    return render(request, "warehouse/warehouse_list.html", {"warehouses": warehouses})


@login_required
@erp_perm("warehouse_manage")
@require_http_methods(["GET", "POST"])
def warehouse_create(request):
    form = WarehouseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Warehouse saved.")
        return redirect("warehouse-list")
    return render(
        request,
        "warehouse/warehouse_form.html",
        {"form": form, "title": "New warehouse"},
    )


@login_required
@erp_perm("warehouse_manage")
@require_http_methods(["GET", "POST"])
def warehouse_edit(request, pk: int):
    wh = get_object_or_404(Warehouse, pk=pk)
    form = WarehouseForm(request.POST or None, instance=wh)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Warehouse updated.")
        return redirect("warehouse-list")
    return render(
        request,
        "warehouse/warehouse_form.html",
        {"form": form, "title": f"Edit {wh.code}", "warehouse": wh},
    )


@login_required
@erp_perm("warehouse_write")
def stock_move_items_partial(request):
    if not getattr(request, "htmx", False):
        return redirect("stock-move")
    raw = (request.GET.get("from_warehouse") or "").strip()
    if not raw.isdigit():
        return render(
            request,
            "warehouse/partials/stock_move_item_slot.html",
            {"stocks": [], "empty_reason": "no_wh"},
        )
    wh = get_object_or_404(Warehouse, pk=int(raw), is_active=True)
    stocks = list(
        WarehouseStock.objects.filter(warehouse=wh, quantity_on_hand__gt=0)
        .select_related("item", "item__uom")
        .order_by("item__sku")
    )
    return render(
        request,
        "warehouse/partials/stock_move_item_slot.html",
        {"stocks": stocks, "from_warehouse": wh},
    )


@login_required
@erp_perm("warehouse_write")
def warehouse_out_items_partial(request):
    if not getattr(request, "htmx", False):
        return redirect("warehouse-out")
    raw = (request.GET.get("warehouse") or "").strip()
    if not raw.isdigit():
        return render(
            request,
            "warehouse/partials/stock_move_item_slot.html",
            {"stocks": [], "empty_reason": "no_wh"},
        )
    wh = get_object_or_404(Warehouse, pk=int(raw), is_active=True)
    stocks = list(
        WarehouseStock.objects.filter(warehouse=wh, quantity_on_hand__gt=0)
        .select_related("item", "item__uom")
        .order_by("item__sku")
    )
    return render(
        request,
        "warehouse/partials/warehouse_out_item_slot.html",
        {"stocks": stocks, "from_warehouse": wh},
    )


@login_required
@erp_perm("warehouse_write")
@require_http_methods(["GET", "POST"])
def warehouse_out(request):
    items_url = reverse("warehouse-out-items")
    if request.method == "POST":
        form = WarehouseOutForm(request.POST, items_partial_url=items_url)
        item_ids = request.POST.getlist("out_item")
        qty_strs = request.POST.getlist("out_qty")
        if not form.is_valid():
            messages.error(request, "Check warehouse, customer, and other fields.")
            return render(
                request,
                "warehouse/warehouse_out.html",
                {"form": form},
                status=400,
            )
        lines: list[tuple[Item, Decimal]] = []
        for raw_id, raw_qty in zip_longest(item_ids, qty_strs, fillvalue=""):
            iid = (raw_id or "").strip()
            if not iid:
                continue
            if not iid.isdigit():
                messages.error(request, "Invalid item selection.")
                return render(
                    request,
                    "warehouse/warehouse_out.html",
                    {"form": form},
                    status=400,
                )
            try:
                qty = Decimal((raw_qty or "").strip())
            except InvalidOperation:
                messages.error(request, "Enter a valid quantity for each line.")
                return render(
                    request,
                    "warehouse/warehouse_out.html",
                    {"form": form},
                    status=400,
                )
            if qty <= 0:
                messages.error(request, "Each line quantity must be greater than zero.")
                return render(
                    request,
                    "warehouse/warehouse_out.html",
                    {"form": form},
                    status=400,
                )
            item = get_object_or_404(Item, pk=int(iid))
            lines.append((item, qty))
        if not lines:
            messages.error(
                request,
                "Add at least one item line (choose a warehouse and pick SKU + qty).",
            )
            return render(
                request,
                "warehouse/warehouse_out.html",
                {"form": form},
                status=400,
            )
        wh = form.cleaned_data["warehouse"]
        try:
            out = record_warehouse_outbound(
                wh,
                form.cleaned_data["customer"],
                lines,
                invoice_number=form.cleaned_data.get("invoice_number") or "",
                ship_to=form.cleaned_data.get("ship_to") or "",
                is_freebie=form.cleaned_data.get("is_freebie", False),
                note=form.cleaned_data.get("note") or "",
                created_by=request.user,
            )
        except ValidationError as e:
            msg = e.messages[0] if e.messages else str(e)
            messages.error(request, msg)
            return render(
                request,
                "warehouse/warehouse_out.html",
                {"form": form},
                status=400,
            )
        fb = " (freebie)" if out.is_freebie else ""
        n = len(lines)
        messages.success(
            request,
            f"{out.out_number}: recorded {n} line(s) from {wh.code}{fb}.",
        )
        return redirect("warehouse-out")
    form = WarehouseOutForm(items_partial_url=items_url)
    return render(request, "warehouse/warehouse_out.html", {"form": form})


@login_required
@erp_perm("warehouse_write")
@require_http_methods(["GET", "POST"])
def stock_move(request):
    items_url = reverse("stock-move-items")
    if request.method == "POST":
        form = StockMoveForm(request.POST, items_partial_url=items_url)
        item_id = (request.POST.get("item") or "").strip()
        qty_raw = (request.POST.get("quantity") or "").strip()
        if not form.is_valid():
            messages.error(request, "Fix the warehouse selections.")
            return render(
                request,
                "warehouse/stock_move.html",
                {"form": form},
                status=400,
            )
        if not item_id.isdigit():
            messages.error(request, "Select an item (choose a source warehouse first).")
            return render(
                request,
                "warehouse/stock_move.html",
                {"form": form},
                status=400,
            )
        try:
            qty = Decimal(qty_raw)
        except InvalidOperation:
            messages.error(request, "Enter a valid quantity.")
            return render(
                request,
                "warehouse/stock_move.html",
                {"form": form},
                status=400,
            )
        if qty <= 0:
            messages.error(request, "Quantity must be greater than zero.")
            return render(
                request,
                "warehouse/stock_move.html",
                {"form": form},
                status=400,
            )
        from_wh = form.cleaned_data["from_warehouse"]
        to_wh = form.cleaned_data["to_warehouse"]
        if from_wh.pk == to_wh.pk:
            messages.error(request, "Source and destination must be different.")
            return render(
                request,
                "warehouse/stock_move.html",
                {"form": form},
                status=400,
            )
        item = get_object_or_404(Item, pk=int(item_id))
        try:
            transfer_between_warehouses(
                item, from_wh, to_wh, qty, created_by=request.user
            )
        except ValidationError as e:
            msg = e.messages[0] if e.messages else str(e)
            messages.error(request, msg)
            return render(
                request,
                "warehouse/stock_move.html",
                {"form": form},
                status=400,
            )
        messages.success(
            request,
            f"Moved {qty} {item.sku} from {from_wh.code} to {to_wh.code}.",
        )
        return redirect("stock-move")
    form = StockMoveForm(items_partial_url=items_url)
    return render(request, "warehouse/stock_move.html", {"form": form})


@login_required
@erp_perm("warehouse_read")
def stock_ledger_list(request):
    qs = StockLedger.objects.select_related(
        "item",
        "item__uom",
        "warehouse",
        "created_by",
    ).order_by("-timestamp", "-pk")
    item_id = (request.GET.get("item") or "").strip()
    if item_id.isdigit():
        qs = qs.filter(item_id=int(item_id))
    wh_id = (request.GET.get("warehouse") or "").strip()
    if wh_id.isdigit():
        qs = qs.filter(warehouse_id=int(wh_id))
    tx = (request.GET.get("tx_type") or "").strip()
    if tx in StockLedger.TxType.values:
        qs = qs.filter(tx_type=tx)

    entries = list(qs[:500])
    return render(
        request,
        "warehouse/stock_ledger_list.html",
        {
            "entries": entries,
            "warehouses": Warehouse.objects.filter(is_active=True).order_by("code"),
            "tx_choices": StockLedger.TxType.choices,
            "filter_item": item_id if item_id.isdigit() else "",
            "filter_warehouse": wh_id if wh_id.isdigit() else "",
            "filter_tx": tx if tx in StockLedger.TxType.values else "",
        },
    )


@login_required
@erp_perm("warehouse_read")
def warehouse_stock(request, pk: int):
    wh = get_object_or_404(Warehouse, pk=pk)
    lines = (
        WarehouseStock.objects.filter(warehouse=wh)
        .select_related("item", "item__uom")
        .order_by("item__sku")
    )
    return render(
        request,
        "warehouse/warehouse_stock.html",
        {"warehouse": wh, "lines": lines},
    )
