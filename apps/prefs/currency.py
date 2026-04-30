from typing import Final

CURRENCY_CHOICES: Final[tuple[tuple[str, str], ...]] = (
    ("USD", "US dollar (USD)"),
    ("EUR", "Euro (EUR)"),
    ("GBP", "Pound sterling (GBP)"),
    ("INR", "Indian rupee (INR)"),
    ("NPR", "Nepalese rupee (NPR)"),
    ("JPY", "Japanese yen (JPY)"),
    ("AUD", "Australian dollar (AUD)"),
    ("CAD", "Canadian dollar (CAD)"),
    ("CHF", "Swiss franc (CHF)"),
    ("CNY", "Chinese yuan (CNY)"),
    ("SGD", "Singapore dollar (SGD)"),
    ("AED", "UAE dirham (AED)"),
)

_SYMBOLS: Final[dict[str, str]] = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "INR": "₹",
    "NPR": "NPR ",
    "JPY": "¥",
    "AUD": "A$",
    "CAD": "C$",
    "CHF": "CHF ",
    "CNY": "¥",
    "SGD": "S$",
    "AED": "د.إ ",
}


def currency_symbol(code: str) -> str:
    c = (code or "USD").upper()
    return _SYMBOLS.get(c, f"{c} ")
