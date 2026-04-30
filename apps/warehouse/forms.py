from django import forms

from .models import Customer, Warehouse

_CTRL = "form-control form-control-sm"
_SEL = "form-select form-select-sm"


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ["name", "code", "address", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": _CTRL}),
            "code": forms.TextInput(attrs={"class": _CTRL}),
            "address": forms.Textarea(attrs={"class": _CTRL, "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class StockMoveForm(forms.Form):
    from_warehouse = forms.ModelChoiceField(
        label="From warehouse",
        queryset=Warehouse.objects.none(),
        widget=forms.Select(
            attrs={
                "class": _SEL,
                "hx-get": "",
                "hx-target": "#stock-move-item-slot",
                "hx-include": "#stock-move-form",
                "hx-trigger": "change",
            }
        ),
    )
    to_warehouse = forms.ModelChoiceField(
        label="To warehouse",
        queryset=Warehouse.objects.none(),
        widget=forms.Select(attrs={"class": _SEL}),
    )

    def __init__(self, *args, items_partial_url: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        wh = Warehouse.objects.filter(is_active=True).order_by("code")
        self.fields["from_warehouse"].queryset = wh
        self.fields["to_warehouse"].queryset = wh
        if items_partial_url:
            self.fields["from_warehouse"].widget.attrs["hx-get"] = items_partial_url


class WarehouseOutForm(forms.Form):
    warehouse = forms.ModelChoiceField(
        label="Ship from warehouse",
        queryset=Warehouse.objects.none(),
        widget=forms.Select(
            attrs={
                "class": _SEL,
                "hx-get": "",
                "hx-target": "#warehouse-out-item-slot",
                "hx-include": "#warehouse-out-form",
                "hx-trigger": "change",
            }
        ),
    )
    customer = forms.ModelChoiceField(
        label="Customer",
        queryset=Customer.objects.none(),
        widget=forms.Select(attrs={"class": _SEL}),
    )
    invoice_number = forms.CharField(
        required=False,
        max_length=80,
        label="Invoice number (optional)",
        widget=forms.TextInput(
            attrs={
                "class": _CTRL,
                "placeholder": "e.g. INV-2026-0142",
            }
        ),
    )
    ship_to = forms.CharField(
        required=False,
        label="Attention (optional)",
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "class": _CTRL,
                "placeholder": "Suite, site contact, delivery notes",
            }
        ),
    )
    is_freebie = forms.BooleanField(
        required=False,
        initial=False,
        label="Freebie (promotional / no charge)",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    note = forms.CharField(
        required=False,
        max_length=300,
        widget=forms.Textarea(attrs={"class": _CTRL, "rows": 2}),
        label="Internal note (optional)",
    )

    def __init__(self, *args, items_partial_url: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        wh = Warehouse.objects.filter(is_active=True).order_by("code")
        self.fields["warehouse"].queryset = wh
        self.fields["customer"].queryset = Customer.objects.filter(
            active=True
        ).order_by("name")
        if items_partial_url:
            self.fields["warehouse"].widget.attrs["hx-get"] = items_partial_url


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "code", "email", "phone", "active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": _CTRL}),
            "code": forms.TextInput(attrs={"class": _CTRL}),
            "email": forms.EmailInput(attrs={"class": _CTRL}),
            "phone": forms.TextInput(attrs={"class": _CTRL}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
