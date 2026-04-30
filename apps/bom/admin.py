from django.contrib import admin

from .models import (
    BillOfMaterials,
    Item,
    ItemPackaging,
    ProductCategory,
    UnitOfMeasure,
    UOMCategory,
)


@admin.register(UOMCategory)
class UOMCategoryAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "abbreviation",
        "category",
        "is_base_unit",
        "conversion_factor",
    ]
    list_filter = ["category", "is_base_unit"]
    search_fields = ["name", "abbreviation"]


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "parent"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ["sku", "name", "category", "uom", "current_stock", "reorder_level"]
    list_filter = ["category"]
    search_fields = ["sku", "name"]


@admin.register(ItemPackaging)
class ItemPackagingAdmin(admin.ModelAdmin):
    list_display = [
        "item",
        "code",
        "name",
        "units_per_package",
        "is_default",
        "active",
    ]
    list_filter = ["active", "is_default"]
    search_fields = ["item__sku", "item__name", "code", "name"]
    autocomplete_fields = ["item"]


@admin.register(BillOfMaterials)
class BillOfMaterialsAdmin(admin.ModelAdmin):
    list_display = [
        "product",
        "component",
        "uom",
        "packaging",
        "quantity_required",
        "scrap_factor",
    ]
    autocomplete_fields = ["product", "component", "uom", "packaging"]
    search_fields = ["product__sku", "component__sku"]
