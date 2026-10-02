from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from compute_market.api.main import app
from compute_market.db.models import Base, Bid, Lease, Order, Provider
from compute_market.db.session import get_session


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)

    def override():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as client:
        yield client, sessions
    app.dependency_overrides.clear()
    engine.dispose()


def test_real_empty_never_becomes_demo(client):
    api, _ = client
    for path in ["orders", "providers", "market/timeseries", "research/observations"]:
        response = api.get(f"/v1/{path}")
        assert response.status_code == 200
        assert response.json()["data"] == []
        assert response.json()["meta"]["mode"] == "live"
    assert api.get("/v1/market/summary").json()["data"]["median_winning_price"] is None


def test_demo_filters_and_export_provenance(client, monkeypatch):
    api, _ = client
    monkeypatch.setenv("DEMO_MODE", "true")
    rows = api.get("/v1/orders?gpu_model=H100&region=us-east&limit=3").json()
    assert rows["meta"]["mode"] == "demo"
    assert len(rows["data"]) == 3
    assert all(row["region"] == "us-east" for row in rows["data"])
    assert api.get("/v1/orders?gpu_model=B200").json()["data"] == []
    detail = api.get(f"/v1/orders/{rows['data'][0]['id']}").json()["data"]
    assert detail["bids"] and detail["provenance"]["synthetic"]
    csv = api.get("/v1/exports/orders.csv?gpu_model=H100")
    assert "synthetic," in csv.text
    assert api.get("/v1/orders/missing").status_code == 404
    assert api.get("/v1/orders?start=2026-01-01T00:00:00").status_code == 422


def test_native_prices_are_not_mislabeled_usd_and_late_bids_excluded(client):
    api, sessions = client
    instant = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with sessions.begin() as session:
        session.add_all(
            [
                Provider(id=p, first_seen_at=instant, last_seen_at=instant)
                for p in ["a", "b"]
            ]
        )
        session.add(
            Order(
                id="akashnet-2/owner/1/1/1",
                owner="owner",
                dseq="1",
                gseq=1,
                oseq=1,
                created_height=1,
                created_at=instant,
                gpu_model="H100",
                gpu_count=1,
            )
        )
        session.flush()
        session.add_all(
            [
                Bid(
                    id="early",
                    order_id="akashnet-2/owner/1/1/1",
                    provider_id="a",
                    created_height=2,
                    created_at=instant,
                    price_amount=Decimal("125.000000000001"),
                    price_denom="uakt",
                    state="active",
                ),
                Bid(
                    id="late",
                    order_id="akashnet-2/owner/1/1/1",
                    provider_id="b",
                    created_height=3,
                    created_at=instant.replace(hour=1),
                    provenance={"tx_index": 2, "event_index": 1},
                    price_amount=Decimal("99"),
                    price_denom="uakt",
                    state="active",
                ),
            ]
        )
        session.add(
            Lease(
                id="lease",
                order_id="akashnet-2/owner/1/1/1",
                provider_id="a",
                created_height=3,
                created_at=instant.replace(hour=1),
                provenance={"tx_index": 1, "event_index": 1},
                winning_bid_price=Decimal("125.000000000001"),
                price_denom="uakt",
            )
        )
    row = api.get("/v1/orders/akashnet-2%2Fowner%2F1%2F1%2F1").json()["data"]
    assert row["bid_count"] == 1
    assert row["lowest_bid"] is None
    assert len(row["bids"]) == 2
    assert row["bids"][0]["price"] is None
    assert row["winner"] == "a"


def test_readiness_checks_database_independently_of_process_health(client):
    api, sessions = client
    assert api.get("/health").status_code == 200
    assert api.get("/ready").status_code == 200
    Order.__table__.drop(sessions.kw["bind"])
    assert api.get("/health").status_code == 200
    response = api.get("/ready")
    assert response.status_code == 503
    assert "No synthetic fallback" in response.json()["detail"]
