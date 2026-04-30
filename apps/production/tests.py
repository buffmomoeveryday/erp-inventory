from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bom.models import BillOfMaterials, Item, UOMCategory, UnitOfMeasure
from apps.production.models import ProductionOrder, StockLedger


class ProductionOrderModelTests(TestCase):
    def setUp(self):
        self.cat = UOMCategory.objects.create(name="Count")
        self.ea = UnitOfMeasure.objects.create(
            name="Each",
            abbreviation="ea",
            category=self.cat,
            is_base_unit=True,
            conversion_factor=Decimal("1"),
        )
        self.raw = Item.objects.create(
            sku="R-PO",
            name="Part",
            uom=self.ea,
            category="RAW",
            current_stock=Decimal("100"),
        )
        self.fin = Item.objects.create(
            sku="F-PO",
            name="Product",
            uom=self.ea,
            category="FIN",
            current_stock=Decimal("0"),
        )
        BillOfMaterials.objects.create(
            product=self.fin,
            component=self.raw,
            uom=self.ea,
            quantity_required=Decimal("2"),
        )

    def test_complete_requires_in_progress(self):
        order = ProductionOrder.objects.create(
            product=self.fin,
            quantity_to_produce=Decimal("1"),
            status=ProductionOrder.Status.DRAFT,
        )
        with self.assertRaises(ValidationError):
            order.complete_production()

    def test_start_without_approval_raises(self):
        order = ProductionOrder.objects.create(
            product=self.fin,
            quantity_to_produce=Decimal("1"),
            status=ProductionOrder.Status.DRAFT,
        )
        with self.assertRaisesMessage(
            ValidationError, "must be approved before it can be started"
        ):
            order.start_production()

    def test_start_then_complete_updates_stock(self):
        order = ProductionOrder.objects.create(
            product=self.fin,
            quantity_to_produce=Decimal("3"),
            status=ProductionOrder.Status.DRAFT,
            approved_at=timezone.now(),
        )
        order.start_production()
        self.assertEqual(order.status, ProductionOrder.Status.IN_PROGRESS)
        order.complete_production()
        order.refresh_from_db()
        self.fin.refresh_from_db()
        self.raw.refresh_from_db()
        self.assertEqual(order.status, ProductionOrder.Status.COMPLETED)
        self.assertEqual(self.fin.current_stock, Decimal("3"))
        self.assertEqual(self.raw.current_stock, Decimal("94"))
        self.assertTrue(
            StockLedger.objects.filter(
                tx_type=StockLedger.TxType.PROD_OUTPUT,
                reference_id=order.batch_number,
            ).exists()
        )
        self.assertTrue(
            StockLedger.objects.filter(
                tx_type=StockLedger.TxType.PROD_CONSUME,
                reference_id=order.batch_number,
            ).exists()
        )


class ProductionViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "p", "p@example.com", "x", is_superuser=True
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.cat = UOMCategory.objects.create(name="C")
        self.ea = UnitOfMeasure.objects.create(
            name="Each",
            abbreviation="ea",
            category=self.cat,
            is_base_unit=True,
            conversion_factor=Decimal("1"),
        )
        self.fin = Item.objects.create(
            sku="FV",
            name="Fin",
            uom=self.ea,
            category="FIN",
        )

    def test_create_and_detail(self):
        url = reverse("production-order-create")
        r = self.client.post(
            url,
            {
                "product": str(self.fin.pk),
                "quantity_to_produce": "5",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(ProductionOrder.objects.count(), 1)
        po = ProductionOrder.objects.get()
        r2 = self.client.get(reverse("production-order-detail", kwargs={"pk": po.pk}))
        self.assertEqual(r2.status_code, 200)

    def test_start_blocked_until_approve(self):
        po = ProductionOrder.objects.create(
            product=self.fin,
            quantity_to_produce=Decimal("1"),
            status=ProductionOrder.Status.DRAFT,
        )
        r = self.client.post(
            reverse("production-order-start", kwargs={"pk": po.pk}),
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        po.refresh_from_db()
        self.assertEqual(po.status, ProductionOrder.Status.DRAFT)
        self.client.post(reverse("production-order-approve", kwargs={"pk": po.pk}))
        po.refresh_from_db()
        self.assertIsNotNone(po.approved_at)
        r2 = self.client.post(
            reverse("production-order-start", kwargs={"pk": po.pk}),
            follow=True,
        )
        self.assertEqual(r2.status_code, 200)
        po.refresh_from_db()
        self.assertEqual(po.status, ProductionOrder.Status.IN_PROGRESS)
