"""Console inventory is provider-wide; GPU model descriptions do not split counts."""

from typing import Any
from datetime import datetime, timezone
import httpx

# "all" preserves the complete response. "online" keeps providers reporting
# isOnline true; they were ~3% of records in October 2026. The policy is stored
# with every snapshot so a filtered one is never mistaken for a small network.
RETENTION_POLICIES = ("all", "online")


def validate_retention(policy: str) -> str:
    if policy not in RETENTION_POLICIES:
        raise ValueError(
            f"Unknown inventory retention policy {policy!r}; expected one of {RETENTION_POLICIES}"
        )
    return policy


def retain_records(payload: list[dict[str, Any]], policy: str) -> list[dict[str, Any]]:
    validate_retention(policy)
    if policy == "online":
        return [record for record in payload if record.get("isOnline") is True]
    return list(payload)


def fetch_inventory(base_url: str, client: httpx.Client) -> list[dict[str, Any]]:
    response = client.get(f"{base_url.rstrip('/')}/v1/providers")
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError(
            "Unexpected providers response: expected array; refusing partial snapshot"
        )
    return payload


def provider_capacity(provider: dict[str, Any]) -> dict[str, Any] | None:
    owner = provider.get("owner")
    if not owner:
        raise ValueError("Provider is missing owner")
    gpu = (provider.get("stats") or {}).get("gpu")
    if not isinstance(gpu, dict):
        return None
    counts = {}
    for key in ("active", "available", "pending", "total"):
        value = gpu.get(key)
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError(f"Invalid {key} GPU count for {owner}")
        counts[key] = value
    observed_at = None
    value = provider.get("lastCheckDate")
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                observed_at = parsed.astimezone(timezone.utc)
        except ValueError:
            pass  # Raw response preserves invalid dates; projection stays unknown.
    online = provider.get("isOnline")
    return {
        "observed_at": observed_at,
        "is_online": online if type(online) is bool else None,
        "provider_id": owner,
        "gpu_model": None,
        "scope": "provider_aggregate",
        **counts,
    }
