from .currency import currency_symbol
from .models import OrganizationSettings


def org_currency(request):
    o = OrganizationSettings.get()
    code = o.currency_code
    return {
        "org_currency_code": code,
        "org_currency_symbol": currency_symbol(code),
    }
