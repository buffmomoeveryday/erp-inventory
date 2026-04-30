from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.bom.models import Item
from apps.warehouse.models import Warehouse
from apps.warehouse.services import (
    adjust_warehouse_stock,
    get_default_warehouse,
    quantity_for_item_at_warehouse,
)


class ProductionOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING = "PENDING", "Pending (Stock Reserved)"
        IN_PROGRESS = "PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    batch_number = models.CharField(max_length=20, unique=True, editable=False)
    product = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        limit_choices_to={"category__in": ["SUB", "FIN"]},
        related_name="production_runs",
    )
    quantity_to_produce = models.DecimalField(max_digits=12, decimal_places=3)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    # Performance Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    actual_duration = models.DurationField(null=True, blank=True)

    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_production_orders",
    )

    # WHERE are we taking the raw materials from?
    source_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="production_withdrawals",
        null=True,
    )

    # WHERE are we putting the finished goods?
    destination_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="production_deposits",
        null=True,
    )

    @transaction.atomic
    def start_production(self):
        """Draft or pending → in progress after a final stock check."""
        if self.status not in (self.Status.DRAFT, self.Status.PENDING):
            raise ValidationError("Only draft or pending orders can be started.")
        if not self.approved_at:
            raise ValidationError(
                "This production order must be approved before it can be started."
            )
        if not self.can_start():
            raise ValidationError("Insufficient raw materials to start this batch.")
        self.status = self.Status.IN_PROGRESS
        self.save()

    def save(self, *args, **kwargs):
        if not self.batch_number:
            from django.db.models import Max

            max_pk = ProductionOrder.objects.aggregate(m=Max("pk"))["m"] or 0
            self.batch_number = f"BAT-{max_pk + 1:06d}"

        # Handle Timing Logic
        if self.status == self.Status.IN_PROGRESS and not self.started_at:
            self.started_at = timezone.now()

        if self.status == self.Status.COMPLETED and not self.completed_at:
            self.completed_at = timezone.now()
            if self.started_at:
                self.actual_duration = self.completed_at - self.started_at

        super().save(*args, **kwargs)

    def can_start(self):
        """Checks availability including scrap/waste factors."""
        wh = self.source_warehouse or get_default_warehouse()
        for bom_item in self.product.bom_parents.select_related("component"):
            required = bom_item.get_required_with_waste(self.quantity_to_produce)
            available = quantity_for_item_at_warehouse(bom_item.component, wh)
            if available < required:
                return False
        return True

    @transaction.atomic
    def complete_production(self):
        """In progress → completed: consume BOM components, add finished output."""
        if self.status == self.Status.COMPLETED:
            return
        if self.status != self.Status.IN_PROGRESS:
            raise ValidationError("Only in-progress orders can be completed.")

        src = self.source_warehouse or get_default_warehouse()
        dst = self.destination_warehouse or get_default_warehouse()
        bom_items = self.product.bom_parents.select_related("component")

        for bom in bom_items:
            total_needed = bom.get_required_with_waste(self.quantity_to_produce)
            adjust_warehouse_stock(
                bom.component,
                src,
                -total_needed,
                tx_type="PROD_CONSUME",
                reference_id=self.batch_number,
            )

        adjust_warehouse_stock(
            self.product,
            dst,
            self.quantity_to_produce,
            tx_type="PROD_OUTPUT",
            reference_id=self.batch_number,
        )

        self.status = self.Status.COMPLETED
        self.save()


class StockLedger(models.Model):
    class TxType(models.TextChoices):
        PURCHASE = "PURCHASE", "Purchase receipt"
        PROD_CONSUME = "PROD_CONSUME", "Production consume"
        PROD_OUTPUT = "PROD_OUTPUT", "Production output"
        STOCK_XFER_OUT = "STOCK_XFER_OUT", "Transfer out"
        STOCK_XFER_IN = "STOCK_XFER_IN", "Transfer in"
        ITEM_OPENING = "ITEM_OPENING", "Item opening stock"
        WAREHOUSE_OUT = "WAREHOUSE_OUT", "Warehouse out (client/buyer)"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"

    item = models.ForeignKey(
        "bom.Item",
        on_delete=models.CASCADE,
        related_name="stock_ledger_entries",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="stock_ledger_entries",
    )
    change_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    tx_type = models.CharField(max_length=20, choices=TxType.choices)
    reference_id = models.CharField(max_length=80)
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_ledger_entries",
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp", "-pk"]
        indexes = [
            models.Index(fields=["item", "-timestamp"]),
            models.Index(fields=["warehouse", "-timestamp"]),
        ]

    def __str__(self):
        wh = self.warehouse.code if self.warehouse_id else "—"
        return f"{self.tx_type} {self.item.sku} @ {wh} {self.change_quantity}"
