from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.warehouse.services import adjust_warehouse_stock, get_default_warehouse

from .models import GoodsReceipt, GoodsReceiptItem, POLineItem, PurchaseOrder


@transaction.atomic
def record_goods_receipt(
    purchase_order: PurchaseOrder,
    receiving_warehouse,
    line_quantities: dict[int, Decimal],
    line_package_quantities: dict[int, Decimal] | None = None,
    reference_note: str = "",
) -> GoodsReceipt:
    if purchase_order.status not in (
        PurchaseOrder.Status.SENT,
        PurchaseOrder.Status.PARTIAL,
    ):
        raise ValidationError("Only sent or partially received orders can be received.")

    wh = receiving_warehouse or get_default_warehouse()
    if wh is None:
        raise ValidationError("Select a receiving warehouse or create a default one.")

    line_package_quantities = line_package_quantities or {}
    total_accepted = Decimal("0")
    for q in line_quantities.values():
        if q and q > 0:
            total_accepted += q
    for q in line_package_quantities.values():
        if q and q > 0:
            total_accepted += q
    if total_accepted <= 0:
        raise ValidationError("Enter at least one positive accepted quantity.")

    receipt = GoodsReceipt.objects.create(
        purchase_order=purchase_order,
        receiving_warehouse=wh,
        reference_note=reference_note or "",
    )

    for line_id in set(line_quantities.keys()) | set(line_package_quantities.keys()):
        qty = line_quantities.get(line_id, Decimal("0"))
        package_qty = line_package_quantities.get(line_id, Decimal("0"))
        if (qty is None or qty <= 0) and (package_qty is None or package_qty <= 0):
            continue
        line = POLineItem.objects.select_for_update().get(
            pk=int(line_id),
            purchase_order=purchase_order,
        )
        if qty is None:
            qty = Decimal("0")
        accepted_total = qty
        accepted_packaging = None
        if package_qty and package_qty > 0:
            if line.packaging_id is None:
                raise ValidationError(
                    f"Line {line.item.sku}: no packaging configured for package receipt."
                )
            accepted_total += package_qty * line.packaging.units_per_package
            accepted_packaging = line.packaging
        remaining = line.quantity_ordered - line.quantity_received
        if accepted_total > remaining:
            raise ValidationError(
                f"Line {line.item.sku}: cannot accept {accepted_total}; remaining is {remaining}."
            )
        GoodsReceiptItem.objects.create(
            receipt=receipt,
            po_line_item=line,
            quantity_accepted=accepted_total,
            packaging=accepted_packaging,
        )
        line.quantity_received += accepted_total
        line.save(update_fields=["quantity_received"])
        adjust_warehouse_stock(
            line.item,
            wh,
            accepted_total,
            tx_type="PURCHASE",
            reference_id=purchase_order.po_number,
        )

    lines = list(
        POLineItem.objects.select_for_update().filter(purchase_order=purchase_order)
    )
    if all(line.quantity_received >= line.quantity_ordered for line in lines):
        purchase_order.status = PurchaseOrder.Status.RECEIVED
    else:
        purchase_order.status = PurchaseOrder.Status.PARTIAL
    purchase_order.save()

    return receipt
