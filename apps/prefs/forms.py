from django import forms

from .models import OrganizationSettings

_CTRL = "form-select form-select-sm"


class OrganizationSettingsForm(forms.ModelForm):
    class Meta:
        model = OrganizationSettings
        fields = ["currency_code"]
        widgets = {"currency_code": forms.Select(attrs={"class": _CTRL})}
