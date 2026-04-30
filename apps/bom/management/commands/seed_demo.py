from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.bom.models import (
    BillOfMaterials,
    Item,
    ItemPackaging,
    ProductCategory,
    UnitOfMeasure,
    UOMCategory,
)
from apps.procurement.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    POLineItem,
    PurchaseOrder,
    Supplier,
)
from apps.production.models import ProductionOrder, StockLedger
from apps.warehouse.models import (
    Customer,
    Warehouse,
    WarehouseOutboundLine,
    WarehouseOutboundShipment,
    WarehouseStock,
)
from apps.warehouse.services import refresh_item_total_stock


class Command(BaseCommand):
    help = (
        "Seed demo data: UOMs, items, BOM, warehouse stock, supplier, PO, production order. "
        "Skips catalog seed if DEMO-* items already exist unless you pass --reset."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete items, BOMs, UOMs, warehouses, stock, procurement, production, then reseed.",
        )

    def _clear(self) -> None:
        self.stdout.write(
            self.style.WARNING("Clearing seeded domains (destructive)...")
        )
        GoodsReceiptItem.objects.all().delete()
        GoodsReceipt.objects.all().delete()
        POLineItem.objects.all().delete()
        PurchaseOrder.objects.all().delete()
        Supplier.objects.all().delete()
        ProductionOrder.objects.all().delete()
        StockLedger.objects.all().delete()
        WarehouseOutboundLine.objects.all().delete()
        WarehouseOutboundShipment.objects.all().delete()
        Customer.objects.all().delete()
        BillOfMaterials.objects.all().delete()
        WarehouseStock.objects.all().delete()
        Item.objects.all().delete()
        UnitOfMeasure.objects.all().delete()
        UOMCategory.objects.all().delete()
        Warehouse.objects.all().delete()
        ProductCategory.objects.all().delete()

    def _put_warehouse_stock(
        self, item: Item, warehouse: Warehouse, qty: Decimal
    ) -> None:
        row, _ = WarehouseStock.objects.get_or_create(
            item=item,
            warehouse=warehouse,
            defaults={"quantity_on_hand": qty},
        )
        if row.quantity_on_hand != qty:
            row.quantity_on_hand = qty
            row.save(update_fields=["quantity_on_hand"])
        refresh_item_total_stock(item)

    def _ensure_core(self) -> tuple[Warehouse, Supplier]:
        wh, wh_created = Warehouse.objects.get_or_create(
            code="MAIN",
            defaults={
                "name": "Main warehouse",
                "address": "",
                "is_active": True,
            },
        )
        if wh_created:
            self.stdout.write(self.style.SUCCESS("Created warehouse MAIN."))
        sup, sup_created = Supplier.objects.get_or_create(
            code="DEMO",
            defaults={
                "name": "Demo supplier",
                "contact_email": "",
                "active": True,
            },
        )
        if sup_created:
            self.stdout.write(self.style.SUCCESS("Created supplier DEMO."))
        for code, name in (
            ("DEMO-RET", "Demo retailer"),
            ("DEMO-B2B", "Demo wholesale"),
        ):
            _, cust_created = Customer.objects.get_or_create(
                code=code,
                defaults={"name": name, "active": True},
            )
            if cust_created:
                self.stdout.write(self.style.SUCCESS(f"Created customer {code}."))
        return wh, sup

    def _seed_catalog(self, warehouse: Warehouse, supplier: Supplier) -> None:
        count_cat, _ = UOMCategory.objects.get_or_create(name="Count")
        each, _ = UnitOfMeasure.objects.get_or_create(
            name="Each",
            category=count_cat,
            defaults={
                "abbreviation": "ea",
                "is_base_unit": True,
                "conversion_factor": Decimal("1"),
            },
        )

        ProductCategory.objects.get_or_create(
            slug="demo-raw",
            defaults={"name": "Demo raw materials", "description": ""},
        )
        ProductCategory.objects.get_or_create(
            slug="demo-finished",
            defaults={"name": "Demo finished goods", "description": ""},
        )

        raw_a, _ = Item.objects.update_or_create(
            sku="DEMO-RAW-A",
            defaults={
                "name": "Demo bracket",
                "uom": each,
                "category": "RAW",
                "standard_cost": Decimal("1.25"),
                "reorder_level": Decimal("50"),
                "current_stock": Decimal("0"),
            },
        )
        raw_b, _ = Item.objects.update_or_create(
            sku="DEMO-RAW-B",
            defaults={
                "name": "Demo panel",
                "uom": each,
                "category": "RAW",
                "standard_cost": Decimal("3.50"),
                "reorder_level": Decimal("30"),
                "current_stock": Decimal("0"),
            },
        )
        sub, _ = Item.objects.update_or_create(
            sku="DEMO-SUB-KIT",
            defaults={
                "name": "Demo sub-assembly kit",
                "uom": each,
                "category": "SUB",
                "standard_cost": Decimal("12.00"),
                "reorder_level": Decimal("10"),
                "current_stock": Decimal("0"),
            },
        )
        fg, _ = Item.objects.update_or_create(
            sku="DEMO-FG-WIDGET",
            defaults={
                "name": "Demo finished widget",
                "uom": each,
                "category": "FIN",
                "standard_cost": Decimal("28.00"),
                "reorder_level": Decimal("5"),
                "current_stock": Decimal("0"),
            },
        )

        self._put_warehouse_stock(raw_a, warehouse, Decimal("400"))
        self._put_warehouse_stock(raw_b, warehouse, Decimal("180"))
        self._put_warehouse_stock(sub, warehouse, Decimal("40"))
        self._put_warehouse_stock(fg, warehouse, Decimal("22"))

        ItemPackaging.objects.update_or_create(
            item=raw_a,
            code="BOX-25",
            defaults={
                "name": "Box of 25",
                "units_per_package": Decimal("25"),
                "is_default": True,
                "active": True,
            },
        )
        ItemPackaging.objects.update_or_create(
            item=raw_b,
            code="BOX-10",
            defaults={
                "name": "Box of 10",
                "units_per_package": Decimal("10"),
                "is_default": True,
                "active": True,
            },
        )

        BillOfMaterials.objects.get_or_create(
            product=sub,
            component=raw_a,
            defaults={
                "uom": each,
                "quantity_required": Decimal("2"),
                "scrap_factor": Decimal("2"),
            },
        )
        BillOfMaterials.objects.get_or_create(
            product=sub,
            component=raw_b,
            defaults={
                "uom": each,
                "quantity_required": Decimal("1"),
                "scrap_factor": Decimal("1"),
            },
        )
        BillOfMaterials.objects.get_or_create(
            product=fg,
            component=sub,
            defaults={
                "uom": each,
                "quantity_required": Decimal("1"),
                "scrap_factor": Decimal("0"),
            },
        )
        BillOfMaterials.objects.get_or_create(
            product=fg,
            component=raw_a,
            defaults={
                "uom": each,
                "quantity_required": Decimal("1"),
                "scrap_factor": Decimal("1"),
            },
        )

        if not PurchaseOrder.objects.filter(supplier=supplier).exists():
            po = PurchaseOrder(supplier=supplier, status=PurchaseOrder.Status.SENT)
            po.save()
            POLineItem.objects.create(
                purchase_order=po,
                item=raw_a,
                quantity_ordered=Decimal("120"),
                quantity_received=Decimal("0"),
                unit_price=Decimal("1.10"),
            )
            POLineItem.objects.create(
                purchase_order=po,
                item=raw_b,
                quantity_ordered=Decimal("60"),
                quantity_received=Decimal("0"),
                unit_price=Decimal("3.25"),
            )
            self.stdout.write(
                self.style.SUCCESS(f"Created purchase order {po.po_number} (sent).")
            )

        if not ProductionOrder.objects.filter(product=fg).exists():
            prod = ProductionOrder(
                product=fg,
                quantity_to_produce=Decimal("8"),
                status=ProductionOrder.Status.DRAFT,
                source_warehouse=warehouse,
                destination_warehouse=warehouse,
            )
            prod.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created production order {prod.batch_number} (draft)."
                )
            )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self._clear()

        warehouse, supplier = self._ensure_core()

        if (
            not options["reset"]
            and Item.objects.filter(sku__startswith="DEMO-").exists()
        ):
            self.stdout.write(
                "Demo catalog already present (SKU prefix DEMO-). Use --reset to wipe and rebuild."
            )
            return

        self._seed_catalog(warehouse, supplier)
        self.stdout.write(self.style.SUCCESS("Demo seed complete."))
