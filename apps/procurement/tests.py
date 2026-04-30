from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from apps.bom.models import Item, ItemPackaging, UOMCategory, UnitOfMeasure
from apps.procurement.models import POLineItem, PurchaseOrder, Supplier
from apps.production.models import StockLedger
from apps.procurement.services import record_goods_receipt
from apps.warehouse.models import Warehouse
from apps.warehouse.services import quantity_for_item_at_warehouse


class GoodsReceiptPackagingTests(TestCase):
    def setUp(self):
        count_cat = UOMCategory.objects.create(name="Count")
        self.ea = UnitOfMeasure.objects.create(
            name="Each",
            abbreviation="ea",
            category=count_cat,
            is_base_unit=True,
            conversion_factor=Decimal("1"),
        )
        self.item = Item.objects.create(
            sku="RAW-PACK",
            name="Packable raw",
            uom=self.ea,
            category="RAW",
            current_stock=Decimal("0"),
        )
        self.pack = ItemPackaging.objects.create(
            item=self.item,
            code="BOX-12",
            name="Box of 12",
            units_per_package=Decimal("12"),
            is_default=True,
        )
        self.supplier = Supplier.objects.create(name="S", code="SUP")
        self.po = PurchaseOrder.objects.create(
            supplier=self.supplier,
            status=PurchaseOrder.Status.SENT,
        )
        self.line = POLineItem.objects.create(
            purchase_order=self.po,
            item=self.item,
            packaging=self.pack,
            quantity_ordered=Decimal("30"),
            unit_price=Decimal("1.00"),
        )
        self.wh = Warehouse.objects.create(name="Main", code="MAIN", is_active=True)

    def test_receipt_supports_package_and_unit_inputs(self):
        record_goods_receipt(
            self.po,
            self.wh,
            line_quantities={self.line.pk: Decimal("6")},
            line_package_quantities={self.line.pk: Decimal("2")},
        )
        self.line.refresh_from_db()
        self.assertEqual(self.line.quantity_received, Decimal("30"))
        self.assertEqual(
            quantity_for_item_at_warehouse(self.item, self.wh),
            Decimal("30"),
        )
        ledgers = StockLedger.objects.filter(
            item=self.item,
            tx_type=StockLedger.TxType.PURCHASE,
            reference_id=self.po.po_number,
        )
        self.assertEqual(ledgers.count(), 1)
        self.assertEqual(ledgers.get().change_quantity, Decimal("30"))

    def test_receipt_without_packaging_rejects_package_quantity(self):
        self.line.packaging = None
        self.line.save(update_fields=["packaging"])
        with self.assertRaisesMessage(ValidationError, "no packaging configured"):
            record_goods_receipt(
                self.po,
                self.wh,
                line_quantities={},
                line_package_quantities={self.line.pk: Decimal("1")},
            )


class PurchaseOrderApprovalViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "buyer", "buyer@example.com", "secret", is_superuser=True
        )
        self.client = Client()
        self.client.force_login(self.user)
        cat = UOMCategory.objects.create(name="Count")
        ea = UnitOfMeasure.objects.create(
            name="Each",
            abbreviation="ea",
            category=cat,
            is_base_unit=True,
            conversion_factor=Decimal("1"),
        )
        self.item = Item.objects.create(
            sku="AP-RAW",
            name="Bolt",
            uom=ea,
            category="RAW",
        )
        self.supplier = Supplier.objects.create(name="Acme", code="ACM")
        self.po = PurchaseOrder.objects.create(
            supplier=self.supplier,
            status=PurchaseOrder.Status.DRAFT,
        )
        POLineItem.objects.create(
            purchase_order=self.po,
            item=self.item,
            quantity_ordered=Decimal("10"),
            unit_price=Decimal("0.50"),
        )

    def test_send_requires_approval_first(self):
        self.client.post(
            reverse("purchase-order-send", kwargs={"pk": self.po.pk}),
            follow=True,
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.DRAFT)
        self.client.post(
            reverse("purchase-order-approve", kwargs={"pk": self.po.pk}),
            follow=True,
        )
        self.po.refresh_from_db()
        self.assertIsNotNone(self.po.approved_at)
        self.assertEqual(self.po.approved_by_id, self.user.pk)
        self.client.post(
            reverse("purchase-order-send", kwargs={"pk": self.po.pk}),
            follow=True,
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.SENT)
