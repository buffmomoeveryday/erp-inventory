from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Max


class Warehouse(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bom_warehouse"

    def __str__(self):
        return f"{self.name} ({self.code})"


class Customer(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class WarehouseStock(models.Model):
    item = models.ForeignKey(
        "bom.Item",
        on_delete=models.CASCADE,
        related_name="warehouse_stocks",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="stock_lines",
    )
    quantity_on_hand = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal("0.000"),
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["item", "warehouse"],
                name="warehousestock_unique_item_warehouse",
            ),
        ]

    def __str__(self):
        return f"{self.item.sku} @ {self.warehouse.code}: {self.quantity_on_hand}"


class WarehouseOutboundShipment(models.Model):
    out_number = models.CharField(max_length=20, unique=True, editable=False)
    invoice_number = models.CharField(max_length=80, blank=True)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="outbound_shipments",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="outbound_shipments",
    )
    ship_to = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional attention (suite, contact on site).",
    )
    is_freebie = models.BooleanField(default=False)
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warehouse_outbound_shipments",
    )

    class Meta:
        ordering = ["-created_at", "-pk"]

    def save(self, *args, **kwargs):
        if not self.out_number:
            max_pk = WarehouseOutboundShipment.objects.aggregate(m=Max("pk"))["m"] or 0
            self.out_number = f"OUT-{max_pk + 1:06d}"
        super().save(*args, **kwargs)

    def __str__(self):
        fb = " (freebie)" if self.is_freebie else ""
        inv = f" inv {self.invoice_number}" if self.invoice_number else ""
        return f"{self.out_number}{inv} {self.customer.code}{fb}"


class WarehouseOutboundLine(models.Model):
    shipment = models.ForeignKey(
        WarehouseOutboundShipment,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item = models.ForeignKey(
        "bom.Item",
        on_delete=models.PROTECT,
        related_name="outbound_lines",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return f"{self.shipment.out_number} {self.item.sku} ×{self.quantity}"
