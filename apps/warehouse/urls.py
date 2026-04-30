from django.urls import path

from . import views

urlpatterns = [
    path("customers/new/", views.customer_create, name="customer-create"),
    path("customers/", views.customer_list, name="customer-list"),
    path("ledger/", views.stock_ledger_list, name="stock-ledger-list"),
    path("out/items/", views.warehouse_out_items_partial, name="warehouse-out-items"),
    path("out/", views.warehouse_out, name="warehouse-out"),
    path("move/items/", views.stock_move_items_partial, name="stock-move-items"),
    path("move/", views.stock_move, name="stock-move"),
    path("", views.warehouse_list, name="warehouse-list"),
    path("new/", views.warehouse_create, name="warehouse-create"),
    path("<int:pk>/edit/", views.warehouse_edit, name="warehouse-edit"),
    path("<int:pk>/stock/", views.warehouse_stock, name="warehouse-stock"),
]
