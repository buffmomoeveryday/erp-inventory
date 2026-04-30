from django.urls import path

from . import views

urlpatterns = [
    path("suppliers/", views.supplier_list, name="supplier-list"),
    path("suppliers/new/", views.supplier_create, name="supplier-create"),
    path("", views.purchase_order_list, name="purchase-order-list"),
    path("new/", views.purchase_order_create, name="purchase-order-create"),
    path("<int:pk>/", views.purchase_order_detail, name="purchase-order-detail"),
    path(
        "<int:pk>/approve/",
        views.purchase_order_approve,
        name="purchase-order-approve",
    ),
    path("<int:pk>/send/", views.purchase_order_send, name="purchase-order-send"),
    path("<int:pk>/cancel/", views.purchase_order_cancel, name="purchase-order-cancel"),
    path(
        "<int:pk>/receive/", views.purchase_order_receive, name="purchase-order-receive"
    ),
]
