import django.db.models.deletion
from django.db import migrations, models


def create_misc_customer_and_backfill(apps, schema_editor):
    Customer = apps.get_model("warehouse", "Customer")
    WarehouseOutbound = apps.get_model("warehouse", "WarehouseOutbound")
    misc, _ = Customer.objects.get_or_create(
        code="MISC",
        defaults={
            "name": "Miscellaneous / legacy",
            "email": "",
            "phone": "",
            "active": True,
        },
    )
    WarehouseOutbound.objects.filter(customer_id__isnull=True).update(
        customer_id=misc.pk
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("warehouse", "0003_warehouse_outbound_and_ledger_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="Customer",
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
                ("name", models.CharField(max_length=200)),
                ("code", models.CharField(max_length=20, unique=True)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="warehouseoutbound",
            name="customer",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="outbounds",
                to="warehouse.customer",
            ),
        ),
        migrations.AlterField(
            model_name="warehouseoutbound",
            name="ship_to",
            field=models.CharField(
                blank=True,
                help_text="Optional attention (suite, contact on site).",
                max_length=200,
            ),
        ),
        migrations.RunPython(create_misc_customer_and_backfill, noop_reverse),
        migrations.AlterField(
            model_name="warehouseoutbound",
            name="customer",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="outbounds",
                to="warehouse.customer",
            ),
        ),
    ]
