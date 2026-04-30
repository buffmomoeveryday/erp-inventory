from django.db.models import QuerySet
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Supplier(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=10, unique=True)
    contact_email = models.EmailField(blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class PurchaseOrder(models.Model):
    items: QuerySet["POLineItem"]

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SENT = "SENT", "Sent/Ordered"
        PARTIAL = "PARTIAL", "Partially Received"
        RECEIVED = "RECEIVED", "Fully Received"
        CANCELLED = "CANCELLED", "Cancelled"

    po_number = models.CharField(max_length=20, unique=True, editable=False)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="purchase_orders"
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    lead_time_duration = models.DurationField(null=True, blank=True)

    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_purchase_orders",
    )

    def save(self, *args, **kwargs):
        if not self.po_number:
            from django.db.models import Max

            max_pk = PurchaseOrder.objects.aggregate(m=Max("pk"))["m"] or 0
            self.po_number = f"PO-{max_pk + 1:06d}"

        if self.status == self.Status.SENT and not self.sent_at:
            self.sent_at = timezone.now()

        if self.status == self.Status.RECEIVED and not self.completed_at:
            self.completed_at = timezone.now()
            if self.sent_at:
                self.lead_time_duration = self.completed_at - self.sent_at

        super().save(*args, **kwargs)

    @property
    def lead_time_days(self):
        if self.lead_time_duration:
            return self.lead_time_duration.days
        return None

    def __str__(self):
        return self.po_number


class POLineItem(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="items"
    )
    item = models.ForeignKey("bom.Item", on_delete=models.PROTECT)
    packaging = models.ForeignKey(
        "bom.ItemPackaging",
        on_delete=models.PROTECT,
        related_name="purchase_order_lines",
        null=True,
        blank=True,
    )
    quantity_ordered = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_received = models.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal("0.000")
    )
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    def clean(self):
        if self.quantity_ordered is not None and self.quantity_ordered <= 0:
            raise ValidationError("Order quantity must be greater than zero.")
        if self.unit_price is not None and self.unit_price < 0:
            raise ValidationError("Unit price cannot be negative.")
        if (
            self.quantity_ordered is not None
            and self.quantity_received is not None
            and self.quantity_received > self.quantity_ordered
        ):
            raise ValidationError("Received cannot exceed ordered.")
        if (
            self.packaging_id
            and self.item_id
            and self.packaging.item_id != self.item_id
        ):
            raise ValidationError(
                "Selected packaging must belong to the selected item."
            )

    @property
    def is_pending(self):
        return self.quantity_ordered > self.quantity_received

    @property
    def quantity_remaining(self):
        return self.quantity_ordered - self.quantity_received


class GoodsReceipt(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="receipts"
    )
    receiving_warehouse = models.ForeignKey(
        "warehouse.Warehouse",
        on_delete=models.PROTECT,
        related_name="goods_receipts",
        null=True,
        blank=True,
    )
    received_at = models.DateTimeField(auto_now_add=True)
    reference_note = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return (
            f"Receipt for {self.purchase_order.po_number} - {self.received_at.date()}"
        )


class GoodsReceiptItem(models.Model):
    receipt = models.ForeignKey(
        GoodsReceipt, on_delete=models.CASCADE, related_name="received_items"
    )
    po_line_item = models.ForeignKey(POLineItem, on_delete=models.CASCADE)
    packaging = models.ForeignKey(
        "bom.ItemPackaging",
        on_delete=models.PROTECT,
        related_name="goods_receipt_lines",
        null=True,
        blank=True,
    )
    quantity_accepted = models.DecimalField(max_digits=12, decimal_places=3)

    def clean(self):
        if self.packaging_id and self.po_line_item_id:
            if self.packaging.item_id != self.po_line_item.item_id:
                raise ValidationError(
                    "Selected packaging must belong to the PO line item."
                )
