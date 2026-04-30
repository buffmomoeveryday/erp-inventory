from django.contrib import admin

from .models import (
    GoodsReceipt,
    GoodsReceiptItem,
    POLineItem,
    PurchaseOrder,
    Supplier,
)


class POLineItemInline(admin.TabularInline):
    model = POLineItem
    extra = 0
    autocomplete_fields = ["item"]


class GoodsReceiptItemInline(admin.TabularInline):
    model = GoodsReceiptItem
    extra = 0
    autocomplete_fields = ["po_line_item"]


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "contact_email", "active"]
    list_filter = ["active"]
    search_fields = ["code", "name", "contact_email"]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ["po_number", "supplier", "status", "approved_at", "created_at"]
    list_filter = ["status"]
    readonly_fields = [
        "po_number",
        "created_at",
        "sent_at",
        "completed_at",
        "lead_time_duration",
        "approved_at",
        "approved_by",
    ]
    autocomplete_fields = ["supplier", "approved_by"]
    search_fields = ["po_number", "supplier__code", "supplier__name"]
    inlines = [POLineItemInline]


@admin.register(POLineItem)
class POLineItemAdmin(admin.ModelAdmin):
    list_display = [
        "purchase_order",
        "item",
        "quantity_ordered",
        "quantity_received",
        "unit_price",
    ]
    autocomplete_fields = ["purchase_order", "item"]
    search_fields = ["purchase_order__po_number", "item__sku"]


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = [
        "purchase_order",
        "receiving_warehouse",
        "received_at",
        "reference_note",
    ]
    list_filter = ["receiving_warehouse"]
    readonly_fields = ["received_at"]
    autocomplete_fields = ["purchase_order", "receiving_warehouse"]
    search_fields = ["purchase_order__po_number", "reference_note"]
    inlines = [GoodsReceiptItemInline]


@admin.register(GoodsReceiptItem)
class GoodsReceiptItemAdmin(admin.ModelAdmin):
    list_display = ["receipt", "po_line_item", "quantity_accepted"]
    autocomplete_fields = ["receipt", "po_line_item"]
