from django.db import migrations, models


def seed_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    ct = ContentType.objects.filter(app_label="users", model="erppermission").first()
    if ct is None:
        return
    qs = Permission.objects.filter(content_type=ct)
    perms = {p.codename: p for p in qs}

    def pick(*codes):
        return [perms[c] for c in codes if c in perms]

    admin, _ = Group.objects.get_or_create(name="Administrator")
    admin.permissions.set(list(qs))

    viewer, _ = Group.objects.get_or_create(name="Viewer")
    viewer.permissions.set(
        pick(
            "view_items",
            "view_bom",
            "warehouse_read",
            "procurement_read",
            "production_read",
        )
    )

    inv, _ = Group.objects.get_or_create(name="Inventory")
    inv.permissions.set(
        pick(
            "view_items",
            "change_items",
            "view_bom",
            "warehouse_read",
            "warehouse_write",
            "warehouse_manage",
        )
    )

    buyer, _ = Group.objects.get_or_create(name="Procurement")
    buyer.permissions.set(
        pick(
            "view_items",
            "view_bom",
            "warehouse_read",
            "procurement_read",
            "procurement_write",
            "procurement_approve",
        )
    )

    prod, _ = Group.objects.get_or_create(name="Production")
    prod.permissions.set(
        pick(
            "view_items",
            "view_bom",
            "warehouse_read",
            "production_read",
            "production_write",
            "production_approve",
        )
    )

    eng, _ = Group.objects.get_or_create(name="BOM engineer")
    eng.permissions.set(
        pick(
            "view_items",
            "change_items",
            "view_bom",
            "change_bom",
            "uom_settings",
            "warehouse_read",
        )
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="ErpPermission",
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
            ],
            options={
                "verbose_name": "ERP permission",
                "default_permissions": (),
                "permissions": [
                    ("view_items", "View item catalog"),
                    ("change_items", "Create and edit items"),
                    ("view_bom", "View BOM and inventory dashboards"),
                    ("change_bom", "Create and edit bills of materials"),
                    ("uom_settings", "Manage UOM categories and units"),
                    ("warehouse_read", "View warehouses, stock levels, and ledger"),
                    ("warehouse_write", "Transfers, outbound shipments, and customers"),
                    ("warehouse_manage", "Create and edit warehouses"),
                    ("procurement_read", "View purchase orders and suppliers"),
                    (
                        "procurement_write",
                        "Create and edit POs, suppliers, and receipts",
                    ),
                    (
                        "procurement_approve",
                        "Approve, send, or cancel purchase orders",
                    ),
                    ("production_read", "View production orders"),
                    ("production_write", "Create and operate production orders"),
                    ("production_approve", "Approve production orders"),
                    ("org_settings", "Organization and currency settings"),
                ],
                "managed": True,
            },
        ),
        migrations.RunPython(seed_groups, noop_reverse),
    ]
