from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.bom.models import Item

from .models import (
    Customer,
    Warehouse,
    WarehouseOutboundLine,
    WarehouseOutboundShipment,
    WarehouseStock,
)


def _tx_type_str(tx_type) -> str:
    v = getattr(tx_type, "value", tx_type)
    return str(v)[:20]


def append_stock_ledger(
    item: Item,
    warehouse: Warehouse | None,
    change_quantity: Decimal,
    tx_type,
    reference_id: str,
    *,
    note: str = "",
    created_by=None,
) -> None:
    if change_quantity == 0:
        return
    from apps.production.models import StockLedger

    StockLedger.objects.create(
        item=item,
        warehouse=warehouse,
        change_quantity=change_quantity,
        tx_type=_tx_type_str(tx_type),
        reference_id=(reference_id or "")[:80],
        note=(note or "")[:200],
        created_by=created_by,
    )


def get_default_warehouse() -> Warehouse | None:
    return Warehouse.objects.filter(is_active=True).order_by("code").first()


def get_or_create_stock_row(item: Item, warehouse: Warehouse) -> WarehouseStock:
    row, _ = WarehouseStock.objects.get_or_create(
        item=item,
        warehouse=warehouse,
        defaults={"quantity_on_hand": Decimal("0.000")},
    )
    return row


@transaction.atomic
def adjust_warehouse_stock(
    item: Item,
    warehouse: Warehouse | None,
    delta: Decimal,
    *,
    tx_type: str = "ADJUSTMENT",
    reference_id: str = "",
    note: str = "",
    created_by=None,
) -> Decimal:
    if warehouse is None:
        warehouse = get_default_warehouse()
    if warehouse is None:
        item.current_stock += delta
        item.save(update_fields=["current_stock"])
        append_stock_ledger(
            item,
            None,
            delta,
            tx_type,
            reference_id or f"ITEM-{item.pk}",
            note=note,
            created_by=created_by,
        )
        return item.current_stock
    row = get_or_create_stock_row(item, warehouse)
    row.quantity_on_hand += delta
    if row.quantity_on_hand < 0:
        row.quantity_on_hand = Decimal("0.000")
    row.save(update_fields=["quantity_on_hand"])
    refresh_item_total_stock(item)
    append_stock_ledger(
        item,
        warehouse,
        delta,
        tx_type,
        reference_id or f"ITEM-{item.pk}",
        note=note,
        created_by=created_by,
    )
    return row.quantity_on_hand


def refresh_item_total_stock(item: Item) -> None:
    qs = WarehouseStock.objects.filter(item=item)
    if not qs.exists():
        return
    total = qs.aggregate(t=Sum("quantity_on_hand"))["t"] or Decimal("0.000")
    Item.objects.filter(pk=item.pk).update(current_stock=total)
    item.current_stock = total


def quantity_for_item_at_warehouse(item: Item, warehouse: Warehouse | None) -> Decimal:
    if warehouse is None:
        return total_quantity_for_item(item)
    row = WarehouseStock.objects.filter(item=item, warehouse=warehouse).first()
    if row is None:
        return Decimal("0.000")
    return row.quantity_on_hand


def total_quantity_for_item(item: Item) -> Decimal:
    agg = WarehouseStock.objects.filter(item=item).aggregate(t=Sum("quantity_on_hand"))[
        "t"
    ]
    if agg is not None:
        return agg
    return item.current_stock or Decimal("0.000")


@transaction.atomic
def record_warehouse_outbound(
    warehouse: Warehouse,
    customer: Customer,
    lines: list[tuple[Item, Decimal]],
    *,
    invoice_number: str = "",
    ship_to: str = "",
    is_freebie: bool = False,
    note: str = "",
    created_by=None,
) -> WarehouseOutboundShipment:
    if not lines:
        raise ValidationError("Add at least one item line.")
    ship_to = (ship_to or "").strip()[:200]
    invoice_number = (invoice_number or "").strip()[:80]
    note = (note or "").strip()[:300]

    for item, quantity in lines:
        if quantity is None or quantity <= 0:
            raise ValidationError("Each line quantity must be greater than zero.")
        row = (
            WarehouseStock.objects.select_for_update()
            .filter(item=item, warehouse=warehouse)
            .first()
        )
        if row is None or row.quantity_on_hand < quantity:
            raise ValidationError(
                f"Insufficient stock for {item.sku} at this warehouse."
            )

    shipment = WarehouseOutboundShipment(
        customer=customer,
        warehouse=warehouse,
        ship_to=ship_to,
        is_freebie=is_freebie,
        note=note,
        invoice_number=invoice_number,
        created_by=created_by,
    )
    shipment.save()

    base_parts = [f"Customer: {customer.name} ({customer.code})"]
    if invoice_number:
        base_parts.append(f"Invoice: {invoice_number}")
    if ship_to:
        base_parts.append(f"Attention: {ship_to[:100]}")
    if is_freebie:
        base_parts.append("Freebie")
    if note:
        base_parts.append(note[:80])

    for item, quantity in lines:
        WarehouseOutboundLine.objects.create(
            shipment=shipment, item=item, quantity=quantity
        )
        line_parts = [*base_parts, f"{item.sku} × {quantity}"]
        ledger_note = " | ".join(line_parts)[:200]
        adjust_warehouse_stock(
            item,
            warehouse,
            -quantity,
            tx_type="WAREHOUSE_OUT",
            reference_id=shipment.out_number,
            note=ledger_note,
            created_by=created_by,
        )
    return shipment


@transaction.atomic
def transfer_between_warehouses(
    item: Item,
    from_warehouse: Warehouse,
    to_warehouse: Warehouse,
    quantity: Decimal,
    *,
    created_by=None,
) -> None:
    if from_warehouse.pk == to_warehouse.pk:
        raise ValidationError("Choose a different destination warehouse.")
    if quantity is None or quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")

    src = (
        WarehouseStock.objects.select_for_update()
        .filter(item=item, warehouse=from_warehouse)
        .first()
    )
    if src is None or src.quantity_on_hand < quantity:
        raise ValidationError(
            "Not enough quantity at the source warehouse for this transfer."
        )

    dst = (
        WarehouseStock.objects.select_for_update()
        .filter(item=item, warehouse=to_warehouse)
        .first()
    )

    src.quantity_on_hand -= quantity
    if src.quantity_on_hand <= 0:
        src.delete()
    else:
        src.save(update_fields=["quantity_on_hand"])

    if dst is None:
        WarehouseStock.objects.create(
            item=item,
            warehouse=to_warehouse,
            quantity_on_hand=quantity,
        )
    else:
        dst.quantity_on_hand += quantity
        dst.save(update_fields=["quantity_on_hand"])

    refresh_item_total_stock(item)
    ref = f"ITEM-{item.pk}"
    append_stock_ledger(
        item,
        from_warehouse,
        -quantity,
        "STOCK_XFER_OUT",
        ref,
        note=f"To {to_warehouse.code}",
        created_by=created_by,
    )
    append_stock_ledger(
        item,
        to_warehouse,
        quantity,
        "STOCK_XFER_IN",
        ref,
        note=f"From {from_warehouse.code}",
        created_by=created_by,
    )
