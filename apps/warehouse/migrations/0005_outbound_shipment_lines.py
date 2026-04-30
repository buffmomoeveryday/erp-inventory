import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_outbounds_to_shipments(apps, schema_editor):
    Old = apps.get_model("warehouse", "WarehouseOutbound")
    Shipment = apps.get_model("warehouse", "WarehouseOutboundShipment")
    Line = apps.get_model("warehouse", "WarehouseOutboundLine")
    for old in Old.objects.all().order_by("id"):
        s = Shipment(
            out_number=old.out_number,
            invoice_number="",
            customer_id=old.customer_id,
            warehouse_id=old.warehouse_id,
            ship_to=old.ship_to or "",
            is_freebie=old.is_freebie,
            note=old.note or "",
            created_by_id=old.created_by_id,
        )
        s.save()
        Shipment.objects.filter(pk=s.pk).update(created_at=old.created_at)
        Line.objects.create(shipment=s, item_id=old.item_id, quantity=old.quantity)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("bom", "0001_initial"),
        ("warehouse", "0004_customer_and_outbound_fk"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WarehouseOutboundShipment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "out_number",
                    models.CharField(editable=False, max_length=20, unique=True),
                ),
                ("invoice_number", models.CharField(blank=True, max_length=80)),
                (
                    "ship_to",
                    models.CharField(
                        blank=True,
                        help_text="Optional attention (suite, contact on site).",
                        max_length=200,
                    ),
                ),
                ("is_freebie", models.BooleanField(default=False)),
                ("note", models.CharField(blank=True, max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="warehouse_outbound_shipments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="outbound_shipments",
                        to="warehouse.customer",
                    ),
                ),
                (
                    "warehouse",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="outbound_shipments",
                        to="warehouse.warehouse",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-pk"],
            },
        ),
        migrations.CreateModel(
            name="WarehouseOutboundLine",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("quantity", models.DecimalField(decimal_places=3, max_digits=12)),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="outbound_lines",
                        to="bom.item",
                    ),
                ),
                (
                    "shipment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lines",
                        to="warehouse.warehouseoutboundshipment",
                    ),
                ),
            ],
            options={
                "ordering": ["pk"],
            },
        ),
        migrations.RunPython(migrate_outbounds_to_shipments, noop_reverse),
        migrations.DeleteModel(
            name="WarehouseOutbound",
        ),
    ]
