import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from model_bakery import baker

from apps.bom.models import (
    BillOfMaterials,
    Item,
    ProductCategory,
    UnitOfMeasure,
    UOMCategory,
)
from apps.warehouse.models import Warehouse


class Command(BaseCommand):
    help = (
        "Clears catalog/warehouse seed data and builds BOMs for Langtang/Lavie cases: "
        "shared preforms (by ml), shared cap, label per product line."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING("Clearing all existing inventory and BOM data...")
        )
        BillOfMaterials.objects.all().delete()
        Item.objects.all().delete()
        UnitOfMeasure.objects.all().delete()
        UOMCategory.objects.all().delete()
        Warehouse.objects.all().delete()
        ProductCategory.objects.all().delete()

        self.stdout.write("Generating core configuration...")
        count_cat = baker.make(UOMCategory, name="Count")
        each = baker.make(
            UnitOfMeasure,
            name="Each",
            abbreviation="ea",
            category=count_cat,
            is_base_unit=True,
            conversion_factor=1.0,
        )

        baker.make(Warehouse, name="Main warehouse", code="MAIN")
        baker.make(ProductCategory, name="Raw Materials", slug="raw")
        baker.make(ProductCategory, name="Finished Cases", slug="fin")

        shared_cap = baker.make(
            Item,
            name="Universal bottle cap",
            sku="RM-CAP-UNIV",
            uom=each,
            category="RAW",
            standard_cost=Decimal("0.02"),
            current_stock=Decimal("100000"),
            reorder_level=Decimal("5000"),
        )

        preforms = {
            "500": baker.make(
                Item,
                name="500ml PET preform",
                sku="RM-PREF-500",
                uom=each,
                category="RAW",
                standard_cost=Decimal("0.05"),
            ),
            "1000": baker.make(
                Item,
                name="1000ml PET preform",
                sku="RM-PREF-1000",
                uom=each,
                category="RAW",
                standard_cost=Decimal("0.08"),
            ),
        }

        labels = {
            "langtang_1000": baker.make(
                Item,
                name="Langtang Grace label (1000ml bottle)",
                sku="RM-LBL-LAN-1000",
                uom=each,
                category="RAW",
                standard_cost=Decimal("0.03"),
            ),
            "lavie_1000": baker.make(
                Item,
                name="Lavie Garden label (1000ml bottle)",
                sku="RM-LBL-LAV-1000",
                uom=each,
                category="RAW",
                standard_cost=Decimal("0.03"),
            ),
            "langtang_500": baker.make(
                Item,
                name="Langtang Grace label (500ml bottle)",
                sku="RM-LBL-LAN-500",
                uom=each,
                category="RAW",
                standard_cost=Decimal("0.02"),
            ),
        }

        # Per finished case: bottles per case × (1 label + 1 preform + 1 cap) for that bottle size.
        # Same RM-PREF-1000 and RM-CAP-UNIV for both 1000ml cases; label differs by brand.
        case_matrix = [
            (
                "Langtang Grace 1000ML (Case of 15 bottles)",
                "FG-LAN-1000-CS15",
                "1000",
                "langtang_1000",
                15,
            ),
            (
                "Lavie Garden 1000ML (Case of 15 bottles)",
                "FG-LAV-1000-CS15",
                "1000",
                "lavie_1000",
                15,
            ),
            (
                "Langtang Grace 500ML (Case of 30 bottles)",
                "FG-LAN-500-CS30",
                "500",
                "langtang_500",
                30,
            ),
        ]

        for name, sku, size_key, label_key, bottles_per_case in case_matrix:
            case_fg = baker.make(
                Item,
                name=name,
                sku=sku,
                uom=each,
                category="FIN",
                standard_cost=Decimal("0.00"),
                current_stock=Decimal(random.randint(20, 100)),
                reorder_level=Decimal("10"),
            )
            preform = preforms[size_key]
            label = labels[label_key]
            n = Decimal(bottles_per_case)

            baker.make(
                BillOfMaterials,
                product=case_fg,
                component=preform,
                uom=each,
                quantity_required=n,
                scrap_factor=Decimal("1.5"),
            )
            baker.make(
                BillOfMaterials,
                product=case_fg,
                component=label,
                uom=each,
                quantity_required=n,
                scrap_factor=Decimal("4.0"),
            )
            baker.make(
                BillOfMaterials,
                product=case_fg,
                component=shared_cap,
                uom=each,
                quantity_required=n,
                scrap_factor=Decimal("0.5"),
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Rebuilt BOMs: 3 case SKUs; shared 500/1000ml preforms + universal cap; labels per line."
            )
        )
