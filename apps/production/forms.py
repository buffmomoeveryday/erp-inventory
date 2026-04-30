from django import forms

from apps.bom.models import Item
from apps.warehouse.models import Warehouse

from .models import ProductionOrder

_SEL = "form-select form-select-sm"
_CTRL = "form-control form-control-sm"


class ProductionOrderForm(forms.ModelForm):
    class Meta:
        model = ProductionOrder
        fields = [
            "product",
            "quantity_to_produce",
            "source_warehouse",
            "destination_warehouse",
        ]
        widgets = {
            "product": forms.Select(attrs={"class": _SEL}),
            "quantity_to_produce": forms.NumberInput(
                attrs={
                    "class": _CTRL,
                    "step": "0.001",
                    "min": "0.001",
                }
            ),
            "source_warehouse": forms.Select(attrs={"class": _SEL}),
            "destination_warehouse": forms.Select(attrs={"class": _SEL}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = (
            Item.objects.filter(category__in=["SUB", "FIN"])
            .select_related("uom")
            .order_by("sku")
        )
        wh = Warehouse.objects.filter(is_active=True).order_by("code")
        self.fields["source_warehouse"].queryset = wh
        self.fields["destination_warehouse"].queryset = wh
        self.fields["source_warehouse"].required = False
        self.fields["destination_warehouse"].required = False
