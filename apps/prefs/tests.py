from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from apps.prefs.currency import currency_symbol
from apps.prefs.models import OrganizationSettings


class OrganizationSettingsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "s",
            "s@example.com",
            "x",
            is_superuser=True,
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_settings_hub_200(self):
        r = self.client.get(reverse("settings-hub"))
        self.assertEqual(r.status_code, 200)

    def test_change_currency(self):
        url = reverse("organization-settings")
        r = self.client.post(url, {"currency_code": "EUR"}, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(OrganizationSettings.get().currency_code, "EUR")


class CurrencyUtilTests(SimpleTestCase):
    def test_unknown_code_includes_iso_letters(self):
        self.assertIn("ZZZ", currency_symbol("ZZZ"))
