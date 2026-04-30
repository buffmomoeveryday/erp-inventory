from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from apps.bom.models import (
    BillOfMaterials,
    Item,
    ItemPackaging,
    UOMCategory,
    UnitOfMeasure,
)
from apps.warehouse.models import Warehouse, WarehouseStock
from apps.production.models import StockLedger
from apps.warehouse.services import transfer_between_warehouses


class BomModelTests(TestCase):
    def setUp(self):
        self.cat = UOMCategory.objects.create(name="Weight")
        self.g = UnitOfMeasure.objects.create(
            name="Gram",
            abbreviation="g",
            category=self.cat,
            is_base_unit=True,
            conversion_factor=Decimal("1"),
        )
        self.kg = UnitOfMeasure.objects.create(
            name="Kilogram",
            abbreviation="kg",
            category=self.cat,
            is_base_unit=False,
            conversion_factor=Decimal("1000"),
        )
        self.count_cat = UOMCategory.objects.create(name="Count")
        self.ea = UnitOfMeasure.objects.create(
            name="Each",
            abbreviation="ea",
            category=self.count_cat,
            is_base_unit=True,
            conversion_factor=Decimal("1"),
        )

        self.raw = Item.objects.create(
            sku="RAW-1",
            name="Powder",
            uom=self.g,
            category="RAW",
        )
        self.fin = Item.objects.create(
            sku="FIN-1",
            name="Case",
            uom=self.ea,
            category="FIN",
        )
        self.raw_pack = ItemPackaging.objects.create(
            item=self.raw,
            code="BOX-100",
            name="Box of 100",
            units_per_package=Decimal("100"),
            is_default=True,
        )

    def test_required_quantity_in_component_stock_uom(self):
        bom = BillOfMaterials(
            product=self.fin,
            component=self.raw,
            uom=self.kg,
            quantity_required=Decimal("1"),
            scrap_factor=Decimal("0"),
        )
        bom.full_clean()
        need = bom.get_required_with_waste(Decimal("2"))
        self.assertEqual(need, Decimal("2000"))

    def test_clean_rejects_self_component(self):
        bom = BillOfMaterials(
            product=self.fin,
            component=self.fin,
            uom=self.ea,
            quantity_required=Decimal("1"),
        )
        with self.assertRaises(ValidationError):
            bom.full_clean()

    def test_clean_rejects_raw_as_product(self):
        bom = BillOfMaterials(
            product=self.raw,
            component=self.fin,
            uom=self.ea,
            quantity_required=Decimal("1"),
        )
        with self.assertRaises(ValidationError):
            bom.full_clean()

    def test_unique_product_component_enforced_in_database(self):
        BillOfMaterials.objects.create(
            product=self.fin,
            component=self.raw,
            uom=self.kg,
            quantity_required=Decimal("1"),
        )
        dup = BillOfMaterials(
            product=self.fin,
            component=self.raw,
            uom=self.kg,
            quantity_required=Decimal("2"),
        )
        with self.assertRaises(IntegrityError):
            dup.save()

    def test_required_quantity_with_packaging_uses_item_specific_units(self):
        bom = BillOfMaterials(
            product=self.fin,
            component=self.raw,
            uom=self.g,
            packaging=self.raw_pack,
            quantity_required=Decimal("2"),
            scrap_factor=Decimal("0"),
        )
        bom.full_clean()
        need = bom.get_required_with_waste(Decimal("3"))
        self.assertEqual(need, Decimal("600"))

    def test_clean_rejects_packaging_from_other_item(self):
        other = Item.objects.create(
            sku="RAW-2",
            name="Other",
            uom=self.g,
            category="RAW",
        )
        wrong_pack = ItemPackaging.objects.create(
            item=other,
            code="BOX-5",
            name="Box of 5",
            units_per_package=Decimal("5"),
        )
        bom = BillOfMaterials(
            product=self.fin,
            component=self.raw,
            uom=self.g,
            packaging=wrong_pack,
            quantity_required=Decimal("1"),
        )
        with self.assertRaises(ValidationError):
            bom.full_clean()


class BomViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "tester", "t@example.com", "secret", is_superuser=True
        )
        self.client = Client()
        self.client.force_login(self.user)

        self.cat = UOMCategory.objects.create(name="Count")
        self.ea = UnitOfMeasure.objects.create(
            name="Each",
            abbreviation="ea",
            category=self.cat,
            is_base_unit=True,
            conversion_factor=Decimal("1"),
        )
        self.raw = Item.objects.create(
            sku="R1",
            name="Cap",
            uom=self.ea,
            category="RAW",
        )
        self.fin = Item.objects.create(
            sku="F1",
            name="Bottle case",
            uom=self.ea,
            category="FIN",
        )

    def test_bom_detail_url_uses_product_id(self):
        BillOfMaterials.objects.create(
            product=self.fin,
            component=self.raw,
            uom=self.ea,
            quantity_required=Decimal("2"),
        )
        url = reverse("bom-detail-dashboard", kwargs={"product_id": self.fin.pk})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_create_bom_post(self):
        url = reverse("create-bom")
        r = self.client.post(
            url,
            {
                "product": str(self.fin.pk),
                "component_id[]": [str(self.raw.pk)],
                "qty[]": ["2"],
                "uom_id[]": [str(self.ea.pk)],
                "scrap[]": ["5"],
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(BillOfMaterials.objects.count(), 1)
        line = BillOfMaterials.objects.get()
        self.assertEqual(line.quantity_required, Decimal("2"))
        self.assertEqual(line.scrap_factor, Decimal("5"))

    def test_create_bom_rejects_second_bom_for_same_product(self):
        BillOfMaterials.objects.create(
            product=self.fin,
            component=self.raw,
            uom=self.ea,
            quantity_required=Decimal("1"),
        )
        url = reverse("create-bom")
        r = self.client.post(
            url,
            {
                "product": str(self.fin.pk),
                "component_id[]": [str(self.raw.pk)],
                "qty[]": ["1"],
                "uom_id[]": [str(self.ea.pk)],
                "scrap[]": ["0"],
            },
        )
        self.assertEqual(r.status_code, 400)

    def test_create_bom_rejects_duplicate_component_lines(self):
        url = reverse("create-bom")
        r = self.client.post(
            url,
            {
                "product": str(self.fin.pk),
                "component_id[]": [str(self.raw.pk), str(self.raw.pk)],
                "qty[]": ["1", "1"],
                "uom_id[]": [str(self.ea.pk), str(self.ea.pk)],
                "scrap[]": ["0", "0"],
            },
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(BillOfMaterials.objects.count(), 0)

    def test_edit_bom_replaces_lines(self):
        BillOfMaterials.objects.create(
            product=self.fin,
            component=self.raw,
            uom=self.ea,
            quantity_required=Decimal("1"),
        )
        url = reverse("edit-bom", kwargs={"product_id": self.fin.pk})
        r = self.client.post(
            url,
            {
                "product": str(self.fin.pk),
                "component_id[]": [str(self.raw.pk)],
                "qty[]": ["3"],
                "uom_id[]": [str(self.ea.pk)],
                "scrap[]": ["0"],
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(BillOfMaterials.objects.count(), 1)
        self.assertEqual(BillOfMaterials.objects.get().quantity_required, Decimal("3"))


class UomSettingsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "uomviewer", "u@example.com", "secret", is_superuser=True
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_uom_settings_hub_redirects_when_anonymous(self):
        self.client.logout()
        r = self.client.get(reverse("uom-settings-hub"))
        self.assertEqual(r.status_code, 302)

    def test_uom_settings_hub_200(self):
        r = self.client.get(reverse("uom-settings-hub"))
        self.assertEqual(r.status_code, 200)

    def test_create_uom_category(self):
        r = self.client.post(
            reverse("uom-category-create"),
            {"name": "Volume"},
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(UOMCategory.objects.filter(name="Volume").exists())

    def test_create_unit_rejects_second_base_in_category(self):
        cat = UOMCategory.objects.create(name="Length")
        UnitOfMeasure.objects.create(
            name="Meter",
            abbreviation="m",
            category=cat,
            is_base_unit=True,
            conversion_factor=Decimal("1"),
        )
        r = self.client.post(
            reverse("uom-create"),
            {
                "name": "Centimeter",
                "abbreviation": "cm",
                "category": str(cat.pk),
                "is_base_unit": "on",
                "conversion_factor": "0.01",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "base unit already exists", status_code=200)
        self.assertEqual(UnitOfMeasure.objects.filter(category=cat).count(), 1)


class ItemCreateWarehouseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "ic", "ic@example.com", "secret", is_superuser=True
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.wh = Warehouse.objects.create(name="Main", code="MAIN2", is_active=True)
        cat = UOMCategory.objects.create(name="Count2")
        self.uom = UnitOfMeasure.objects.create(
            name="Each",
            abbreviation="ea",
            category=cat,
            is_base_unit=True,
            conversion_factor=Decimal("1"),
        )

    def test_create_item_places_opening_stock_in_warehouse(self):
        r = self.client.post(
            reverse("item-create"),
            {
                "sku": "WHS-1",
                "name": "Widget",
                "uom": str(self.uom.pk),
                "category": "RAW",
                "stock_warehouse": str(self.wh.pk),
                "current_stock": "25",
                "standard_cost": "1.00",
                "reorder_level": "0",
            },
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        item = Item.objects.get(sku="WHS-1")
        self.assertEqual(item.current_stock, Decimal("25"))
        ws = WarehouseStock.objects.get(item=item, warehouse=self.wh)
        self.assertEqual(ws.quantity_on_hand, Decimal("25"))

    def test_create_item_writes_opening_ledger(self):
        r = self.client.post(
            reverse("item-create"),
            {
                "sku": "LED-OPEN",
                "name": "Led item",
                "uom": str(self.uom.pk),
                "category": "RAW",
                "stock_warehouse": str(self.wh.pk),
                "current_stock": "12",
                "standard_cost": "0",
                "reorder_level": "0",
            },
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        item = Item.objects.get(sku="LED-OPEN")
        self.assertTrue(
            StockLedger.objects.filter(
                item=item,
                tx_type=StockLedger.TxType.ITEM_OPENING,
                change_quantity=Decimal("12"),
            ).exists()
        )


class ItemWarehouseTransferTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "tr", "tr@example.com", "secret", is_superuser=True
        )
        self.client = Client()
        self.client.force_login(self.user)
        cat = UOMCategory.objects.create(name="CountTr")
        self.uom = UnitOfMeasure.objects.create(
            name="Each",
            abbreviation="ea",
            category=cat,
            is_base_unit=True,
            conversion_factor=Decimal("1"),
        )
        self.item = Item.objects.create(
            sku="TR-ITEM",
            name="Transfer test",
            uom=self.uom,
            category="RAW",
            current_stock=Decimal("100"),
        )
        self.wa = Warehouse.objects.create(name="East", code="EAST", is_active=True)
        self.wb = Warehouse.objects.create(name="West", code="WEST", is_active=True)
        WarehouseStock.objects.create(
            item=self.item,
            warehouse=self.wa,
            quantity_on_hand=Decimal("100"),
        )

    def test_transfer_service_moves_quantity(self):
        transfer_between_warehouses(self.item, self.wa, self.wb, Decimal("35"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("100"))
        self.assertEqual(
            WarehouseStock.objects.get(
                item=self.item, warehouse=self.wa
            ).quantity_on_hand,
            Decimal("65"),
        )
        self.assertEqual(
            WarehouseStock.objects.get(
                item=self.item, warehouse=self.wb
            ).quantity_on_hand,
            Decimal("35"),
        )

    def test_transfer_all_removes_source_row(self):
        transfer_between_warehouses(self.item, self.wa, self.wb, Decimal("100"))
        self.assertFalse(
            WarehouseStock.objects.filter(item=self.item, warehouse=self.wa).exists()
        )
        self.assertEqual(
            WarehouseStock.objects.get(
                item=self.item, warehouse=self.wb
            ).quantity_on_hand,
            Decimal("100"),
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("100"))

    def test_transfer_via_item_edit_view(self):
        url = reverse("item-edit", kwargs={"pk": self.item.pk})
        r = self.client.post(
            url,
            {
                "from_warehouse": str(self.wa.pk),
                "to_warehouse": str(self.wb.pk),
                "quantity": "40",
                "transfer_stock": "1",
            },
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(
            WarehouseStock.objects.get(
                item=self.item, warehouse=self.wa
            ).quantity_on_hand,
            Decimal("60"),
        )
        self.assertEqual(
            WarehouseStock.objects.get(
                item=self.item, warehouse=self.wb
            ).quantity_on_hand,
            Decimal("40"),
        )
        xfer = StockLedger.objects.filter(
            item=self.item, reference_id=f"ITEM-{self.item.pk}"
        )
        self.assertEqual(xfer.count(), 2)
        self.assertEqual(
            xfer.filter(tx_type=StockLedger.TxType.STOCK_XFER_OUT)
            .get()
            .change_quantity,
            Decimal("-40"),
        )
