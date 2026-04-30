from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.warehouse.models import WarehouseStock
from apps.warehouse.services import transfer_between_warehouses

from apps.bom.forms import ItemForm, ItemStockTransferForm
from apps.bom.models import Item
from apps.users.decorators import erp_perm


def _item_edit_context(item, form, transfer_form):
    rows = list(
        WarehouseStock.objects.filter(item=item)
        .select_related("warehouse")
        .order_by("warehouse__code")
    )
    return {
        "form": form,
        "transfer_form": transfer_form,
        "warehouse_rows": rows,
        "can_transfer": any(r.quantity_on_hand > 0 for r in rows),
    }


@login_required
@erp_perm("view_items")
def item_list(request):
    items = Item.objects.select_related("uom").order_by("sku")
    return render(request, "bom/item_list.html", {"items": items})


@login_required
@erp_perm("change_items")
@require_http_methods(["GET", "POST"])
def item_create(request):
    form = ItemForm(
        request.POST or None,
        for_create=True,
        ledger_user=request.user if request.user.is_authenticated else None,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Item {form.instance.sku} created.")
        return redirect("item-list")
    return render(
        request,
        "bom/item_form.html",
        {"form": form, "title": "New item", "submit_label": "Create item"},
    )


@login_required
@erp_perm("change_items")
@require_http_methods(["GET", "POST"])
def item_edit(request, pk: int):
    item = get_object_or_404(Item.objects.select_related("uom"), pk=pk)
    if request.method == "POST" and request.POST.get("transfer_stock"):
        if not request.user.has_perm("users.warehouse_write"):
            messages.error(
                request,
                "You need warehouse access to transfer stock between warehouses.",
            )
            return redirect("item-edit", pk=item.pk)
        tform = ItemStockTransferForm(request.POST, item=item)
        form = ItemForm(instance=item)
        if tform.is_valid():
            try:
                transfer_between_warehouses(
                    item,
                    tform.cleaned_data["from_warehouse"],
                    tform.cleaned_data["to_warehouse"],
                    tform.cleaned_data["quantity"],
                    created_by=request.user,
                )
                messages.success(request, "Stock transferred between warehouses.")
                return redirect("item-edit", pk=item.pk)
            except ValidationError as e:
                msg = e.messages[0] if e.messages else str(e)
                messages.error(request, msg)
        return render(
            request,
            "bom/item_form.html",
            {
                **_item_edit_context(item, form, tform),
                "title": f"Edit {item.sku}",
                "submit_label": "Save changes",
                "item": item,
            },
        )

    form = ItemForm(request.POST or None, instance=item)
    tform = ItemStockTransferForm(item=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Item {form.instance.sku} updated.")
        return redirect("item-list")
    return render(
        request,
        "bom/item_form.html",
        {
            **_item_edit_context(item, form, tform),
            "title": f"Edit {item.sku}",
            "submit_label": "Save changes",
            "item": item,
        },
    )
