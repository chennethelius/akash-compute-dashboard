"""Capacity-only hourly observations until marketplace decoding is validated."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text
from compute_market.analytics.metrics import concentration, utilization
from compute_market.db.models import CapacitySnapshot, MarketMetricHourly
from compute_market.db.session import SessionLocal


def aggregate_capacity_hour(hour: datetime, freshness_minutes: int = 20) -> dict:
    if freshness_minutes <= 0:
        raise ValueError("Freshness must be positive")
    if hour.tzinfo is None or hour.minute or hour.second or hour.microsecond:
        raise ValueError("Provide a timezone-aware hour boundary")
    hour_end = hour.astimezone(timezone.utc) + timedelta(hours=1)
    current_time = datetime.now(timezone.utc)
    if hour > current_time:
        raise ValueError("Cannot aggregate a future hour")
    cutoff = min(hour_end, current_time)
    start = cutoff - timedelta(minutes=freshness_minutes)
    key = f"capacity-v1:{hour.astimezone(timezone.utc).isoformat()}"
    with SessionLocal.begin() as session:
        if session.bind.dialect.name == "postgresql":
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:name))"), {"name": key}
            )
        rows = session.scalars(
            select(CapacitySnapshot)
            .where(
                CapacitySnapshot.collected_at >= start,
                CapacitySnapshot.collected_at < cutoff,
                CapacitySnapshot.scope == "provider_aggregate",
            )
            .order_by(CapacitySnapshot.collected_at.desc())
        ).all()
        latest = {}
        for row in rows:
            latest.setdefault(row.provider_id, row)

        def utc(value):
            # SQLite drops offsets; PostgreSQL retains them. Stored timestamps are UTC.
            return (
                value.replace(tzinfo=timezone.utc)
                if value.tzinfo is None
                else value.astimezone(timezone.utc)
            )

        fresh = [
            r
            for r in latest.values()
            if r.is_online is True
            and r.observed_at is not None
            and start <= utc(r.observed_at) <= utc(r.collected_at)
        ]
        complete = [
            r
            for r in fresh
            if r.active is not None and r.available is not None and r.total is not None
        ]
        active = sum(r.active for r in complete) if complete else None
        available = sum(r.available for r in complete) if complete else None
        metrics = {
            "active_gpus": active,
            "available_gpus": available,
            "total_gpus": sum(r.total for r in complete) if complete else None,
            "utilization": utilization(active, available),
            "active_provider_count": sum(r.total > 0 for r in complete),
            "observed_provider_count": len(latest),
            "excluded_incomplete_provider_count": len(fresh) - len(complete),
            "excluded_stale_or_offline_provider_count": len(latest) - len(fresh),
            "freshness_minutes": freshness_minutes,
            "scope": "provider_aggregate",
            "provisional": cutoff < hour_end,
            "observation_cutoff": cutoff.isoformat(),
            "concentration_basis": "reported_total_capacity",
            "marketplace_decoding": "pending",
            **concentration({r.provider_id: r.total for r in complete}),
        }
        metrics["provider_hhi"] = metrics.pop("hhi")
        row = session.get(MarketMetricHourly, key)
        if row is None:
            session.add(
                MarketMetricHourly(
                    id=key,
                    timestamp=hour,
                    gpu_model=None,
                    region=None,
                    definition_version="capacity-v1",
                    metrics=metrics,
                )
            )
        else:
            row.metrics = metrics
        return metrics
