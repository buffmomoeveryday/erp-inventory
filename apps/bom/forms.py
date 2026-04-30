from decimal import Decimal

from django import forms

from apps.warehouse.models import Warehouse, WarehouseStock
from apps.warehouse.services import (
    append_stock_ledger,
    get_or_create_stock_row,
    quantity_for_item_at_warehouse,
    refresh_item_total_stock,
)

from .models import Item, UOMCategory, UnitOfMeasure

_CTRL = "form-control form-control-sm"
_SEL = "form-select form-select-sm"


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            "sku",
            "name",
            "uom",
            "category",
            "current_stock",
            "standard_cost",
            "reorder_level",
        ]
        widgets = {
            "sku": forms.TextInput(attrs={"class": _CTRL}),
            "name": forms.TextInput(attrs={"class": _CTRL}),
            "uom": forms.Select(attrs={"class": _SEL}),
            "category": forms.Select(attrs={"class": _SEL}),
            "current_stock": forms.NumberInput(attrs={"class": _CTRL, "step": "0.001"}),
            "standard_cost": forms.NumberInput(attrs={"class": _CTRL, "step": "0.01"}),
            "reorder_level": forms.NumberInput(attrs={"class": _CTRL, "step": "0.001"}),
        }

    def __init__(self, *args, for_create=False, ledger_user=None, **kwargs):
        self.for_create = for_create
        self.ledger_user = ledger_user
        super().__init__(*args, **kwargs)
        self.fields["uom"].queryset = UnitOfMeasure.objects.select_related(
            "category"
        ).order_by("category__name", "name")
        if for_create:
            self.fields["stock_warehouse"] = forms.ModelChoiceField(
                label="Warehouse for opening stock",
                queryset=Warehouse.objects.filter(is_active=True).order_by("code"),
                required=False,
                widget=forms.Select(attrs={"class": _SEL}),
                help_text="If set, opening quantity is stored at this warehouse and on-hand totals stay in sync.",
            )
            self.fields[
                "current_stock"
            ].help_text = "Opening quantity: either catalog-only (no warehouse) or placed in the warehouse above."
            order = [
                "sku",
                "name",
                "uom",
                "category",
                "stock_warehouse",
                "current_stock",
                "standard_cost",
                "reorder_level",
            ]
            self.fields = {k: self.fields[k] for k in order if k in self.fields}

    def save(self, commit=True):
        instance = super().save(commit=False)
        wh = self.cleaned_data.get("stock_warehouse") if self.for_create else None
        if commit:
            instance.save()
            if self.for_create and wh is not None:
                qty = instance.current_stock or Decimal("0")
                if qty > 0:
                    row = get_or_create_stock_row(instance, wh)
                    row.quantity_on_hand = qty
                    row.save(update_fields=["quantity_on_hand"])
                    refresh_item_total_stock(instance)
                    append_stock_ledger(
                        instance,
                        wh,
                        qty,
                        "ITEM_OPENING",
                        instance.sku,
                        note="Opening stock on item create",
                        created_by=self.ledger_user,
                    )
        return instance


class ItemStockTransferForm(forms.Form):
    from_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),
        label="From warehouse",
        widget=forms.Select(attrs={"class": _SEL}),
    )
    to_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),
        label="To warehouse",
        widget=forms.Select(attrs={"class": _SEL}),
    )
    quantity = forms.DecimalField(
        label="Quantity to move",
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0.001"),
        widget=forms.NumberInput(
            attrs={"class": _CTRL, "step": "0.001", "min": "0.001"}
        ),
    )

    def __init__(self, *args, item: Item | None = None, **kwargs):
        self.item = item
        super().__init__(*args, **kwargs)
        if item is None:
            return
        src_ids = WarehouseStock.objects.filter(
            item=item, quantity_on_hand__gt=0
        ).values_list("warehouse_id", flat=True)
        self.fields["from_warehouse"].queryset = Warehouse.objects.filter(
            pk__in=src_ids,
            is_active=True,
        ).order_by("code")
        self.fields["to_warehouse"].queryset = Warehouse.objects.filter(
            is_active=True
        ).order_by("code")

    def clean(self):
        cleaned = super().clean()
        if self.item is None:
            return cleaned
        fw = cleaned.get("from_warehouse")
        tw = cleaned.get("to_warehouse")
        qty = cleaned.get("quantity")
        if fw and tw and fw.pk == tw.pk:
            raise forms.ValidationError("Source and destination must be different.")
        if fw and qty is not None:
            available = quantity_for_item_at_warehouse(self.item, fw)
            if qty > available:
                raise forms.ValidationError(
                    "Quantity exceeds stock at the source warehouse."
                )
        return cleaned


class UOMCategoryForm(forms.ModelForm):
    class Meta:
        model = UOMCategory
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"class": _CTRL})}


class UnitOfMeasureForm(forms.ModelForm):
    class Meta:
        model = UnitOfMeasure
        fields = [
            "name",
            "abbreviation",
            "category",
            "is_base_unit",
            "conversion_factor",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": _CTRL}),
            "abbreviation": forms.TextInput(attrs={"class": _CTRL}),
            "category": forms.Select(attrs={"class": _SEL}),
            "is_base_unit": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "conversion_factor": forms.NumberInput(
                attrs={"class": _CTRL, "step": "0.000001"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = UOMCategory.objects.order_by("name")
