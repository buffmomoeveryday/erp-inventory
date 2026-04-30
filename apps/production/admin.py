from django.contrib import admin

from .models import ProductionOrder, StockLedger


@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = [
        "batch_number",
        "product",
        "quantity_to_produce",
        "status",
        "approved_at",
        "source_warehouse",
        "destination_warehouse",
        "created_at",
    ]
    list_filter = ["status"]
    readonly_fields = [
        "batch_number",
        "created_at",
        "started_at",
        "completed_at",
        "approved_at",
        "approved_by",
    ]
    autocomplete_fields = [
        "product",
        "source_warehouse",
        "destination_warehouse",
        "approved_by",
    ]
    search_fields = ["batch_number", "product__sku"]


@admin.register(StockLedger)
class StockLedgerAdmin(admin.ModelAdmin):
    list_display = [
        "timestamp",
        "item",
        "warehouse",
        "change_quantity",
        "tx_type",
        "reference_id",
        "created_by",
    ]
    list_filter = ["tx_type", "warehouse"]
    autocomplete_fields = ["item", "warehouse", "created_by"]
    search_fields = ["reference_id", "item__sku", "note"]
    readonly_fields = ["timestamp"]
