from django.db import models


class ErpPermission(models.Model):
    """Placeholder model whose Meta.permissions define ERP feature gates."""

    class Meta:
        managed = True
        default_permissions = ()
        verbose_name = "ERP permission"
        permissions = [
            ("view_items", "View item catalog"),
            ("change_items", "Create and edit items"),
            ("view_bom", "View BOM and inventory dashboards"),
            ("change_bom", "Create and edit bills of materials"),
            ("uom_settings", "Manage UOM categories and units"),
            ("warehouse_read", "View warehouses, stock levels, and ledger"),
            ("warehouse_write", "Transfers, outbound shipments, and customers"),
            ("warehouse_manage", "Create and edit warehouses"),
            ("procurement_read", "View purchase orders and suppliers"),
            ("procurement_write", "Create and edit POs, suppliers, and receipts"),
            ("procurement_approve", "Approve, send, or cancel purchase orders"),
            ("production_read", "View production orders"),
            ("production_write", "Create and operate production orders"),
            ("production_approve", "Approve production orders"),
            ("org_settings", "Organization and currency settings"),
        ]
