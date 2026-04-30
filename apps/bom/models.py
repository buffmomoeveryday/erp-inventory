from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class UOMCategory(models.Model):
    """Examples: Weight, Volume, Length, Count"""

    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "UOM Category"


class UnitOfMeasure(models.Model):
    # e.g., Gram, Kilogram
    name = models.CharField(max_length=50)
    # e.g., g, kg
    abbreviation = models.CharField(max_length=10)
    category = models.ForeignKey(
        UOMCategory, on_delete=models.CASCADE, related_name="units"
    )

    # Is this the reference unit for the category? (e.g., Gram is base for Weight)
    is_base_unit = models.BooleanField(default=False)

    # How many base units are in this unit?
    # If Gram is base, Kilogram conversion_factor = 1000.0
    conversion_factor = models.DecimalField(
        max_digits=12, decimal_places=6, default=Decimal("1.00")
    )

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"

    def clean(self):
        # Ensure only one base unit exists per category
        if self.is_base_unit:
            exists = (
                UnitOfMeasure.objects.filter(category=self.category, is_base_unit=True)
                .exclude(id=self.pk)
                .exists()
            )
            if exists:
                raise ValidationError(
                    f"A base unit already exists for {self.category.name}"
                )


class ProductCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Product Categories"

    def __str__(self):
        if self.parent:
            return f"{self.parent} > {self.name}"
        return self.name


class Item(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)

    uom = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT)
    current_stock = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal("0.00"),
    )

    category = models.CharField(
        max_length=3,
        choices=[
            ("RAW", "Raw"),
            ("SUB", "Sub"),
            ("FIN", "Finished"),
        ],
        default="RAW",
    )

    standard_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    reorder_level = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal("10.00"),
    )

    def __str__(self):
        return f"{self.sku} — {self.name}"


class ItemPackaging(models.Model):
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="packagings",
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    units_per_package = models.DecimalField(max_digits=12, decimal_places=3)
    is_default = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["item", "code"],
                name="itempackaging_unique_item_code",
            ),
            models.UniqueConstraint(
                fields=["item"],
                condition=Q(is_default=True),
                name="itempackaging_single_default_per_item",
            ),
        ]

    def clean(self):
        if self.units_per_package <= 0:
            raise ValidationError("Units per package must be greater than zero.")

    def __str__(self):
        return (
            f"{self.item.sku} — {self.name} ({self.units_per_package} "
            f"{self.item.uom.abbreviation})"
        )


class BillOfMaterials(models.Model):
    product = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name="bom_parents"
    )
    component = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name="bom_components"
    )

    # Allow the user to specify the component requirement in a specific UOM
    # e.g., required 5 'Kilograms' even if the item is tracked in 'Grams'
    uom = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT)
    packaging = models.ForeignKey(
        ItemPackaging,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bom_lines",
    )
    quantity_required = models.DecimalField(max_digits=10, decimal_places=3)

    scrap_factor = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Percentage of material lost during production (e.g., 5.00 for 5%)",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "component"],
                name="bom_unique_component_per_product",
            ),
        ]

    def get_base_quantity(self):
        """Quantity for one output unit, in UOM category base units."""
        if self.packaging:
            # Packaging conversion is already in component stock UOM units.
            return self.quantity_required * self.packaging.units_per_package
        return self.quantity_required * self.uom.conversion_factor

    def get_required_base_with_waste(self, quantity_to_produce):
        return (
            self.get_base_quantity()
            * quantity_to_produce
            * (Decimal("1") + self.scrap_factor / Decimal("100"))
        )

    def get_required_with_waste(self, quantity_to_produce):
        """Total component need in the same UOM as ``component.current_stock``."""
        if self.packaging:
            return self.get_required_base_with_waste(quantity_to_produce)
        base = self.get_required_base_with_waste(quantity_to_produce)
        cu = self.component.uom.conversion_factor
        if cu == 0:
            raise ValidationError("Component UOM conversion factor must be non-zero.")
        return base / cu

    def clean(self):
        if (
            self.product.pk
            and self.component.pk
            and self.product.pk == self.component.pk
        ):
            raise ValidationError("A product cannot be a component of itself.")
        if self.product.pk and self.product.category not in ("FIN", "SUB"):
            raise ValidationError("BOM output must be a finished good or sub-assembly.")
        if self.packaging and self.component:
            if self.packaging.item.pk != self.component.pk:
                raise ValidationError(
                    "Selected packaging must belong to the selected component item."
                )
        if self.uom and self.component:
            if self.packaging:
                return
            if self.uom.category.pk != self.component.uom.category:
                raise ValidationError(
                    f"Cannot use {self.uom.name} for item tracked in "
                    f"{self.component.uom.category.name}"
                )
