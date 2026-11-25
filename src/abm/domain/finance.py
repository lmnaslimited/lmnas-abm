from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


SCALE_TO_UNITS = {
    "unit": Decimal("1"), "units": Decimal("1"),
    "thousand": Decimal("1000"), "thousands": Decimal("1000"),
    "million": Decimal("1000000"), "millions": Decimal("1000000"),
    "billion": Decimal("1000000000"), "billions": Decimal("1000000000"),
}


@dataclass(frozen=True)
class NormalizedRevenue:
    reported_amount: Decimal
    currency: str | None
    scale: str
    revenue_usd_m: Decimal | None
    exchange_rate: Decimal | None
    rate_date: str | None
    source: str | None
    confidence: str | None


def normalize_revenue(amount, currency, scale, *, exchange_rate=None, rate_date=None, source=None, confidence=None):
    """Normalize a reported amount to USD millions; unknown currency stays unconverted."""
    try:
        reported = Decimal(str(amount))
        rate = Decimal(str(exchange_rate)) if exchange_rate is not None else None
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("amount and exchange_rate must be decimal values") from exc
    if not reported.is_finite() or (rate is not None and (not rate.is_finite() or rate <= 0)):
        raise ValueError("amount must be finite and exchange_rate must be positive")
    factor = SCALE_TO_UNITS.get(str(scale).strip().casefold())
    if factor is None:
        raise ValueError(f"unsupported financial scale: {scale!r}")
    code = str(currency).strip().upper() if currency is not None and str(currency).strip() else None
    usd_m = None
    if code == "USD":
        usd_m = reported * factor / Decimal("1000000")
    elif code and rate is not None:
        # The provided exchange rate is defined as USD per one unit of reported currency.
        usd_m = reported * factor * rate / Decimal("1000000")
    return NormalizedRevenue(reported, code, str(scale), usd_m, rate, rate_date, source, confidence)

