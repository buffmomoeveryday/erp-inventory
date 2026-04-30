from django.urls import path

from .views import (
    add_bom_row,
    bom_dashboard,
    bom_detail_dashboard,
    create_bom,
    edit_bom,
    inventory_dashboard,
    uom_settings_views,
    item_views,
)

urlpatterns = [
    path(
        "settings/",
        uom_settings_views.uom_settings_hub,
        name="uom-settings-hub",
    ),
    path(
        "settings/uom-categories/",
        uom_settings_views.uom_category_list,
        name="uom-category-list",
    ),
    path(
        "settings/uom-categories/new/",
        uom_settings_views.uom_category_create,
        name="uom-category-create",
    ),
    path(
        "settings/uom-categories/<int:pk>/edit/",
        uom_settings_views.uom_category_edit,
        name="uom-category-edit",
    ),
    path("settings/units/", uom_settings_views.uom_list, name="uom-list"),
    path("settings/units/new/", uom_settings_views.uom_create, name="uom-create"),
    path(
        "settings/units/<int:pk>/edit/",
        uom_settings_views.uom_edit,
        name="uom-edit",
    ),
    path("", bom_dashboard, name="bom-dashboard"),
    path("inventory/", inventory_dashboard, name="inventory-dashboard"),
    path("create/", create_bom, name="create-bom"),
    path("edit/<int:product_id>/", edit_bom, name="edit-bom"),
    path("add-row/", add_bom_row, name="add_bom_row"),
    path("<int:product_id>/", bom_detail_dashboard, name="bom-detail-dashboard"),
    path("", item_views.item_list, name="item-list"),
    path("new/", item_views.item_create, name="item-create"),
    path("<int:pk>/edit/", item_views.item_edit, name="item-edit"),
]
