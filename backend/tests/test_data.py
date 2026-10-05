from decimal import Decimal
import httpx
import pytest
from compute_market.analytics.metrics import utilization, concentration, bid_dispersion
from compute_market.normalization.prices import bundle_gpu_hour_price
from compute_market.ingestion.inventory.client import provider_capacity
from compute_market.ingestion.chain.client import ChainClient


def sqlite_engine():
    from sqlalchemy import create_engine, event

    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


def test_concentration_empty_equal_and_monopoly():
    assert concentration({})["hhi"] is None
    assert concentration({"a": 1, "b": 1}) == {"hhi": 0.5, "effective_providers": 2}
    assert concentration({"a": 10, "b": 0})["hhi"] == 1
    with pytest.raises(ValueError):
        concentration({"a": -1})


def test_capacity_missing_is_not_zero_and_pending_is_excluded():
    assert utilization(None, 0) is None
    assert utilization(0, 0) is None
    assert utilization(8, 2) == 0.8
    capacity = provider_capacity(
        {
            "owner": "a",
            "gpuModels": [{"model": "h100"}, {"model": "a100"}],
            "stats": {"gpu": {"active": 8, "available": 2, "pending": 1, "total": 11}},
        }
    )
    assert capacity["gpu_model"] is None
    assert capacity["scope"] == "provider_aggregate"
    assert provider_capacity({"owner": "a"}) is None


def test_price_conversion_requires_explicit_fx():
    result = bundle_gpu_hour_price(
        Decimal("1000"),
        denomination_scale=Decimal(1_000_000),
        observed_seconds_per_block=Decimal(6),
        gpu_count=2,
    )
    assert result == {
        "native_bundle_per_gpu_hour": Decimal("0.3"),
        "usd_bundle_per_gpu_hour": None,
    }
    assert (
        bid_dispersion([Decimal(1), Decimal(2), Decimal(3)])["normalized_spread"] == 1
    )
    assert bid_dispersion([])["spread"] is None


def test_rpc_rejects_mismatched_chain():
    def respond(request):
        result = (
            {"block": {"header": {"chain_id": "wrong", "height": "1"}}}
            if request.url.path == "/block"
            else {"height": "1"}
        )
        return httpx.Response(200, json={"result": result})

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        with pytest.raises(ValueError, match="mismatched"):
            ChainClient("https://rpc.test", http).block_pair("akashnet-2", 1)


def test_archive_resume_does_not_duplicate_and_failure_does_not_advance(monkeypatch):
    from sqlalchemy import select, func
    from sqlalchemy.orm import sessionmaker
    from compute_market.db.models import Base, RawBlock, Checkpoint
    from compute_market.jobs import cli

    engine = sqlite_engine()
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    monkeypatch.setattr(cli, "SessionLocal", sessions)
    calls = []

    def pair(self, chain_id, height):
        calls.append(height)
        if height == 3:
            raise ValueError("missing historical block")
        return (
            {"result": {"block": {"header": {"time": "2026-01-01T00:00:00Z"}}}},
            {"result": {"height": str(height)}},
        )

    monkeypatch.setattr(cli.ChainClient, "block_pair", pair)
    assert cli.archive_chain("https://rpc.test", "test", 1, 2) == 2
    assert cli.archive_chain("https://rpc.test", "test", 1, 2) == 0
    with pytest.raises(ValueError):
        cli.archive_chain("https://rpc.test", "test", 1, 3)
    with sessions() as session:
        assert session.get(Checkpoint, "chain:test:1").height == 2
        assert session.scalar(select(func.count()).select_from(RawBlock)) == 2
    assert calls == [1, 2, 3]


def test_hourly_uses_latest_fresh_observation_and_is_idempotent(monkeypatch):
    from datetime import datetime, timezone
    from sqlalchemy import select, func
    from sqlalchemy.orm import sessionmaker
    from compute_market.db.models import (
        Base,
        CapacitySnapshot,
        MarketMetricHourly,
        Provider,
    )
    from compute_market.jobs import hourly

    engine = sqlite_engine()
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    monkeypatch.setattr(hourly, "SessionLocal", sessions)
    hour = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with sessions.begin() as session:
        for provider in ("a", "b", "c", "offline", "stale"):
            session.add(Provider(id=provider, first_seen_at=hour, last_seen_at=hour))
        session.flush()
        session.add(
            CapacitySnapshot(
                provider_id="offline",
                collected_at=hour.replace(minute=45),
                observed_at=hour.replace(minute=45),
                is_online=True,
                active=100,
                available=0,
                total=100,
                pending=0,
                scope="provider_aggregate",
                source="test",
            )
        )
        session.add(
            CapacitySnapshot(
                provider_id="offline",
                collected_at=hour.replace(minute=55),
                observed_at=hour.replace(minute=55),
                is_online=False,
                active=100,
                available=0,
                total=100,
                pending=0,
                scope="provider_aggregate",
                source="test",
            )
        )
        session.add(
            CapacitySnapshot(
                provider_id="stale",
                collected_at=hour.replace(minute=55),
                observed_at=hour.replace(minute=1),
                is_online=True,
                active=100,
                available=0,
                total=100,
                pending=0,
                scope="provider_aggregate",
                source="test",
            )
        )
        for provider, minute, active, available, total in [
            ("a", 45, 2, 8, 10),
            ("a", 55, 8, 2, 10),
            ("b", 20, 100, 0, 100),
            ("c", 50, None, 2, 2),
        ]:
            session.add(
                CapacitySnapshot(
                    provider_id=provider,
                    collected_at=hour.replace(minute=minute),
                    observed_at=hour.replace(minute=minute),
                    is_online=True,
                    active=active,
                    available=available,
                    total=total,
                    pending=0,
                    scope="provider_aggregate",
                    source="test",
                )
            )
    result = hourly.aggregate_capacity_hour(hour)
    assert result["utilization"] == 0.8
    assert result["active_gpus"] == 8
    assert result["provider_hhi"] == 1
    assert result["excluded_incomplete_provider_count"] == 1
    assert result["excluded_stale_or_offline_provider_count"] == 2
    hourly.aggregate_capacity_hour(hour)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(MarketMetricHourly)) == 1


def test_worker_waits_after_failure_and_stops(monkeypatch):
    from compute_market.jobs import worker

    calls = []

    class Stop:
        stopped = False

        def is_set(self):
            return self.stopped

        def wait(self, seconds):
            calls.append(seconds)
            self.stopped = True

    def fail(url, retention):
        calls.append(url)
        raise ValueError("transient failure")

    monkeypatch.setattr(worker, "collect_once", fail)
    worker.run_worker("https://test", 600, Stop())
    assert calls == ["https://test", 600]


def test_inventory_preserves_metadata_and_source_freshness(monkeypatch):
    from datetime import datetime, timezone
    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker
    from compute_market.db.models import Base, Provider, CapacitySnapshot
    from compute_market.jobs import cli

    engine = sqlite_engine()
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    monkeypatch.setattr(cli, "SessionLocal", sessions)
    payload = [
        {
            "owner": "provider",
            "name": "Research host",
            "ipRegion": "Virginia",
            "isOnline": False,
            "lastCheckDate": "2026-01-01T00:00:00Z",
            "attributes": [{"key": "host", "value": "test"}],
            "stats": {"gpu": {"active": 1, "available": 2, "pending": 0, "total": 3}},
        }
    ]
    monkeypatch.setattr(cli, "fetch_inventory", lambda base_url, http: payload)
    assert cli.snapshot_inventory("https://test") == 1
    with sessions() as session:
        provider = session.get(Provider, "provider")
        assert provider.name == "Research host"
        assert provider.region == "Virginia"
        assert provider.attributes["reported_attributes"] == payload[0]["attributes"]
        capacity = session.scalar(select(CapacitySnapshot))
        assert capacity.observed_at.replace(tzinfo=timezone.utc) == datetime(
            2026, 1, 1, tzinfo=timezone.utc
        )
        assert capacity.is_online is False
        assert capacity.raw_snapshot_id
    assert (
        provider_capacity({**payload[0], "lastCheckDate": "bad-date"})["observed_at"]
        is None
    )


def test_inventory_online_retention_records_policy_and_counts(monkeypatch):
    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker
    from compute_market.db.models import Base, CapacitySnapshot, Provider, RawSnapshot
    from compute_market.ingestion.inventory.client import retain_records
    from compute_market.jobs import cli

    engine = sqlite_engine()
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    monkeypatch.setattr(cli, "SessionLocal", sessions)
    online = {
        "owner": "online",
        "isOnline": True,
        "lastCheckDate": "2026-01-01T00:00:00Z",
        "stats": {"gpu": {"active": 1, "available": 1, "pending": 0, "total": 2}},
    }
    offline = {**online, "owner": "offline", "isOnline": False}
    unknown = {**online, "owner": "unknown", "isOnline": None}
    monkeypatch.setattr(
        cli, "fetch_inventory", lambda base_url, http: [online, offline, unknown]
    )
    assert cli.snapshot_inventory("https://test", "online") == 1
    with sessions() as session:
        raw = session.scalar(select(RawSnapshot))
        assert raw.retention_policy == "online"
        assert (raw.source_record_count, raw.retained_record_count) == (3, 1)
        assert [record["owner"] for record in raw.payload] == ["online"]
        assert session.scalars(select(Provider.id)).all() == ["online"]
        assert session.scalars(select(CapacitySnapshot.provider_id)).all() == ["online"]
    with pytest.raises(ValueError):
        retain_records([], "gpu")
    with pytest.raises(ValueError):
        cli.snapshot_inventory("https://test", "gpu")
