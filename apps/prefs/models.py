from django.db import models

from .currency import CURRENCY_CHOICES


class OrganizationSettings(models.Model):
    currency_code = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default="USD",
    )

    class Meta:
        verbose_name = "Organization settings"
        verbose_name_plural = "Organization settings"

    def __str__(self):
        return f"Organization ({self.currency_code})"

    @classmethod
    def get(cls) -> "OrganizationSettings":
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={"currency_code": "USD"},
        )
        return obj
