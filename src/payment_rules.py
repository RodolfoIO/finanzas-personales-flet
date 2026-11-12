from __future__ import annotations

import re
import unicodedata
from datetime import date


PAYMENT_KEYWORDS = (
    "pago",
    "pagotarjeta",
    "abono",
    "payment",
    "credit card payment",
    "tarjeta de credito",
    "tarjeta credito",
    "transferencia a tarjeta",
)


def normalize_payment_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", without_accents.lower()).strip()


def is_card_payment_description(value: str) -> bool:
    text = normalize_payment_text(value)
    compact = text.replace(" ", "")
    return any(keyword in text or keyword in compact for keyword in PAYMENT_KEYWORDS)


def days_between(first: str, second: str) -> int:
    try:
        return abs((date.fromisoformat(first) - date.fromisoformat(second)).days)
    except ValueError:
        return 999999
