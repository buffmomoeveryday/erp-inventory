from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from apps.bom.models import Item, UOMCategory, UnitOfMeasure
from apps.production.models import StockLedger
from apps.warehouse.models import (
    Customer,
    Warehouse,
    WarehouseOutboundLine,
    WarehouseOutboundShipment,
    WarehouseStock,
)
from apps.warehouse.services import record_warehouse_outbound


class StockMoveHtmxTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "mv", "mv@example.com", "secret", is_superuser=True
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.wa = Warehouse.objects.create(name="East", code="MV-E", is_active=True)
        self.wb = Warehouse.objects.create(name="West", code="MV-W", is_active=True)
        cat = UOMCategory.objects.create(name="Cmv")
        uom = UnitOfMeasure.objects.create(
            name="Each",
            abbreviation="ea",
            category=cat,
            is_base_unit=True,
            conversion_factor=Decimal("1"),
        )
        self.item = Item.objects.create(
            sku="MV-SKU",
            name="Movable",
            uom=uom,
            category="RAW",
            current_stock=Decimal("50"),
        )
        WarehouseStock.objects.create(
            item=self.item,
            warehouse=self.wa,
            quantity_on_hand=Decimal("50"),
        )

    def test_items_partial_requires_htmx(self):
        r = self.client.get(
            reverse("stock-move-items"), {"from_warehouse": str(self.wa.pk)}
        )
        self.assertEqual(r.status_code, 302)

    def test_items_partial_returns_options(self):
        r = self.client.get(
            reverse("stock-move-items"),
            {"from_warehouse": str(self.wa.pk)},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "MV-SKU")

    def test_post_move_transfers(self):
        r = self.client.post(
            reverse("stock-move"),
            {
                "from_warehouse": str(self.wa.pk),
                "to_warehouse": str(self.wb.pk),
                "item": str(self.item.pk),
                "quantity": "15",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            WarehouseStock.objects.get(
                item=self.item, warehouse=self.wa
            ).quantity_on_hand,
            Decimal("35"),
        )
        self.assertEqual(
            WarehouseStock.objects.get(
                item=self.item, warehouse=self.wb
            ).quantity_on_hand,
            Decimal("15"),
        )
        self.assertTrue(
            StockLedger.objects.filter(
                item=self.item, tx_type=StockLedger.TxType.STOCK_XFER_IN
            ).exists()
        )


class WarehouseOutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "wo", "wo@example.com", "secret", is_superuser=True
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.wh = Warehouse.objects.create(name="Hub", code="WO-H", is_active=True)
        cat = UOMCategory.objects.create(name="Cow")
        uom = UnitOfMeasure.objects.create(
            name="Each",
            abbreviation="ea",
            category=cat,
            is_base_unit=True,
            conversion_factor=Decimal("1"),
        )
        self.item = Item.objects.create(
            sku="WO-SKU",
            name="Out item",
            uom=uom,
            category="FIN",
            current_stock=Decimal("20"),
        )
        WarehouseStock.objects.create(
            item=self.item,
            warehouse=self.wh,
            quantity_on_hand=Decimal("20"),
        )
        self.customer = Customer.objects.create(
            name="Acme Retail",
            code="ACME",
            active=True,
        )

    def test_record_outbound_deducts_and_ledger(self):
        out = record_warehouse_outbound(
            self.wh,
            self.customer,
            [(self.item, Decimal("5"))],
            invoice_number="INV-9",
            ship_to="Receiving dock A",
            is_freebie=True,
            created_by=self.user,
        )
        self.assertTrue(out.is_freebie)
        self.assertEqual(out.customer_id, self.customer.pk)
        self.assertEqual(out.ship_to, "Receiving dock A")
        self.assertEqual(out.invoice_number, "INV-9")
        self.assertEqual(out.lines.count(), 1)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("15"))
        row = WarehouseStock.objects.get(item=self.item, warehouse=self.wh)
        self.assertEqual(row.quantity_on_hand, Decimal("15"))
        led = StockLedger.objects.get(
            item=self.item,
            tx_type=StockLedger.TxType.WAREHOUSE_OUT,
            reference_id=out.out_number,
        )
        self.assertEqual(led.change_quantity, Decimal("-5"))
        self.assertIn("Freebie", led.note)
        self.assertIn("Acme Retail", led.note)
        self.assertIn("ACME", led.note)
        self.assertIn("INV-9", led.note)

    def test_warehouse_out_form_post(self):
        r = self.client.post(
            reverse("warehouse-out"),
            {
                "warehouse": str(self.wh.pk),
                "customer": str(self.customer.pk),
                "invoice_number": "SO-1001",
                "ship_to": "Buyer One",
                "is_freebie": "on",
                "note": "",
                "out_item": str(self.item.pk),
                "out_qty": "3",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(WarehouseOutboundShipment.objects.count(), 1)
        o = WarehouseOutboundShipment.objects.get()
        self.assertTrue(o.is_freebie)
        self.assertEqual(o.customer_id, self.customer.pk)
        self.assertEqual(o.ship_to, "Buyer One")
        self.assertEqual(o.invoice_number, "SO-1001")
        self.assertEqual(WarehouseOutboundLine.objects.count(), 1)

    def test_warehouse_out_multi_line(self):
        item_b = Item.objects.create(
            sku="WO-SKU-B",
            name="Second",
            uom=self.item.uom,
            category="FIN",
            current_stock=Decimal("10"),
        )
        WarehouseStock.objects.create(
            item=item_b,
            warehouse=self.wh,
            quantity_on_hand=Decimal("10"),
        )
        r = self.client.post(
            reverse("warehouse-out"),
            {
                "warehouse": str(self.wh.pk),
                "customer": str(self.customer.pk),
                "invoice_number": "INV-MULTI",
                "ship_to": "",
                "note": "",
                "out_item": [str(self.item.pk), str(item_b.pk)],
                "out_qty": ["2", "4"],
            },
        )
        self.assertEqual(r.status_code, 302)
        ship = WarehouseOutboundShipment.objects.get()
        self.assertEqual(ship.invoice_number, "INV-MULTI")
        self.assertEqual(ship.lines.count(), 2)
        self.assertEqual(
            WarehouseStock.objects.get(
                item=self.item, warehouse=self.wh
            ).quantity_on_hand,
            Decimal("18"),
        )
        self.assertEqual(
            WarehouseStock.objects.get(item=item_b, warehouse=self.wh).quantity_on_hand,
            Decimal("6"),
        )
