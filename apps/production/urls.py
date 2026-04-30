from django.urls import path

from . import views

urlpatterns = [
    path("", views.production_order_list, name="production-order-list"),
    path("new/", views.production_order_create, name="production-order-create"),
    path("<int:pk>/", views.production_order_detail, name="production-order-detail"),
    path(
        "<int:pk>/approve/",
        views.production_order_approve,
        name="production-order-approve",
    ),
    path(
        "<int:pk>/start/", views.production_order_start, name="production-order-start"
    ),
    path(
        "<int:pk>/complete/",
        views.production_order_complete,
        name="production-order-complete",
    ),
    path(
        "<int:pk>/cancel/",
        views.production_order_cancel,
        name="production-order-cancel",
    ),
]
