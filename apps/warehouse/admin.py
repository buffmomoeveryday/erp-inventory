from django.contrib import admin

from .models import (
    Customer,
    Warehouse,
    WarehouseOutboundLine,
    WarehouseOutboundShipment,
    WarehouseStock,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "email", "phone", "active"]
    list_filter = ["active"]
    search_fields = ["code", "name", "email"]


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["code", "name"]


@admin.register(WarehouseStock)
class WarehouseStockAdmin(admin.ModelAdmin):
    list_display = ["warehouse", "item", "quantity_on_hand"]
    list_filter = ["warehouse"]
    autocomplete_fields = ["warehouse", "item"]
    search_fields = ["item__sku", "warehouse__code"]


class WarehouseOutboundLineInline(admin.TabularInline):
    model = WarehouseOutboundLine
    extra = 0
    autocomplete_fields = ["item"]


@admin.register(WarehouseOutboundShipment)
class WarehouseOutboundShipmentAdmin(admin.ModelAdmin):
    list_display = [
        "out_number",
        "invoice_number",
        "customer",
        "warehouse",
        "is_freebie",
        "created_at",
    ]
    list_filter = ["warehouse", "is_freebie", "customer"]
    search_fields = [
        "out_number",
        "invoice_number",
        "note",
        "customer__code",
        "customer__name",
    ]
    readonly_fields = ["out_number", "created_at"]
    autocomplete_fields = ["customer", "warehouse", "created_by"]
    inlines = [WarehouseOutboundLineInline]
