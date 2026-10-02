"""Pure research definitions. Missing observations never imply zero."""

from decimal import Decimal
import math
from statistics import median
from typing import Iterable, Mapping


def utilization(active: int | None, available: int | None) -> float | None:
    """Allocation proxy, not GPU chip load; pending capacity is excluded."""
    if active is None or available is None:
        return None
    if min(active, available) < 0:
        raise ValueError("Capacity cannot be negative")
    return active / (active + available) if active + available else None


def concentration(provider_weights: Mapping[str, float]) -> dict[str, float | None]:
    """HHI on [0, 1]; caller must identify weight basis and observation window."""
    if any(not math.isfinite(w) or w < 0 for w in provider_weights.values()):
        raise ValueError("Weights must be finite and nonnegative")
    total = sum(provider_weights.values())
    if not total:
        return {"hhi": None, "effective_providers": None}
    hhi = sum((w / total) ** 2 for w in provider_weights.values())
    return {"hhi": hhi, "effective_providers": 1 / hhi}


def bid_dispersion(prices: Iterable[Decimal]) -> dict[str, Decimal | None]:
    """Comparable bids only: same order, denomination, and auction cutoff."""
    values = list(prices)
    if any(not p.is_finite() or p < 0 for p in values):
        raise ValueError("Prices must be finite and nonnegative")
    if not values:
        return {"spread": None, "normalized_spread": None, "median": None}
    mid = median(values)
    spread = max(values) - min(values)
    return {
        "spread": spread,
        "normalized_spread": spread / mid if mid else None,
        "median": mid,
    }
