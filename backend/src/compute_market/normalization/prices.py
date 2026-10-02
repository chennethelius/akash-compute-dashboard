"""Explicit bundle-price conversion; no assumed exchange rate or block interval."""
from decimal import Decimal


def bundle_gpu_hour_price(
    amount_per_block: Decimal,
    *,
    denomination_scale: Decimal,
    observed_seconds_per_block: Decimal,
    gpu_count: int,
    usd_per_token: Decimal | None = None,
) -> dict[str, Decimal | None]:
    for value in (amount_per_block, denomination_scale, observed_seconds_per_block):
        if not value.is_finite():
            raise ValueError("Inputs must be finite")
    if amount_per_block < 0 or denomination_scale <= 0 or observed_seconds_per_block <= 0 or gpu_count <= 0:
        raise ValueError("Invalid price, scale, block interval or GPU count")
    if usd_per_token is not None and (not usd_per_token.is_finite() or usd_per_token <= 0):
        raise ValueError("FX rate must be finite and positive")
    native = amount_per_block / denomination_scale * Decimal(3600) / observed_seconds_per_block / gpu_count
    return {"native_bundle_per_gpu_hour": native, "usd_bundle_per_gpu_hour": native * usd_per_token if usd_per_token is not None else None}
