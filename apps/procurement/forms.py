from django import forms
from django.forms import inlineformset_factory

from apps.bom.models import Item, ItemPackaging

from .models import POLineItem, PurchaseOrder, Supplier

_CTRL = "form-control form-control-sm"
_SEL = "form-select form-select-sm"
_common_num = {"class": _CTRL, "step": "0.001"}
_common_money = {"class": _CTRL, "step": "0.01"}


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "code", "contact_email", "active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": _CTRL}),
            "code": forms.TextInput(attrs={"class": _CTRL}),
            "contact_email": forms.EmailInput(attrs={"class": _CTRL}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["supplier"]
        widgets = {"supplier": forms.Select(attrs={"class": _SEL})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.filter(
            active=True
        ).order_by("code")


class POLineItemForm(forms.ModelForm):
    class Meta:
        model = POLineItem
        fields = ["item", "packaging", "quantity_ordered", "unit_price"]
        widgets = {
            "item": forms.Select(attrs={"class": _SEL}),
            "packaging": forms.Select(attrs={"class": _SEL}),
            "quantity_ordered": forms.NumberInput(attrs=_common_num),
            "unit_price": forms.NumberInput(attrs=_common_money),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = Item.objects.select_related("uom").order_by(
            "sku"
        )
        self.fields["packaging"].required = False
        self.fields["packaging"].queryset = ItemPackaging.objects.filter(
            active=True
        ).select_related("item")


POLineFormSet = inlineformset_factory(
    PurchaseOrder,
    POLineItem,
    form=POLineItemForm,
    extra=2,
    can_delete=True,
    min_num=0,
    validate_min=False,
)
