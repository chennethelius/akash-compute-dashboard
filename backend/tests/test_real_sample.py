"""Reconcile source fixtures through storage, replay, and the public API."""

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from compute_market.api.main import app
from compute_market.db.models import (
    Base,
    Bid,
    BlockProjection,
    Lease,
    MarketplaceEvent,
    Order,
)
from compute_market.db.session import get_session
from compute_market.jobs import decode, sample

FIXTURES = Path(__file__).parent / "fixtures" / "akash"


def test_real_sample_replay_and_order_drilldown(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    monkeypatch.setattr(sample, "SessionLocal", sessions)
    monkeypatch.setattr(decode, "SessionLocal", sessions)
    monkeypatch.setenv("DEMO_MODE", "false")
    first = sample.load_sample(FIXTURES)

    def counts():
        with sessions() as session:
            return [
                session.scalar(select(func.count()).select_from(model))
                for model in [Order, Bid, Lease, MarketplaceEvent, BlockProjection]
            ]

    before = counts()
    assert sample.load_sample(FIXTURES) == first
    assert counts() == before
    assert (
        first["partial_blocks"] > 0
    )  # The fixture window has explicit missing antecedents.

    def get_test_session():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    try:
        with TestClient(app) as client:
            manifest = json.loads((FIXTURES / "manifest.json").read_text())
            response = client.get(f"/v1/orders/{manifest['selected_order_id']}")
            assert response.status_code == 200
            assert response.json()["meta"]["mode"] == "live"
            order = response.json()["data"]
            expected = manifest["selected_order"]
            for key in [
                "gpu_model",
                "gpu_count",
                "memory_bytes",
                "storage_bytes",
                "bid_count",
            ]:
                assert order[key] == expected[key]
            assert order["winner"] == expected["winning_provider"]
            assert {bid["native_price"] for bid in order["bids"]} == {
                "282.496994000000000000",
                "265.753915000000000000",
            }
            assert all(bid["price"] is None for bid in order["bids"])
            assert sum(bid["is_winner"] for bid in order["bids"]) == 1
            assert (
                order["leases"][0]["winning_bid_price"]
                == expected["winning_bid_amount"]
            )
            assert order["leases"][0]["closed_at"] is None
            assert order["created_at"].endswith(("Z", "+00:00"))
            assert order["provenance"]["tx_hash"]
            assert (
                order["provenance"]["source_event"]["type"]
                == "akash.market.v1.EventOrderCreated"
            )
            assert all(value is None for value in order["market_at_order"].values())
            failed_order = client.get(
                "/v1/orders/akashnet-2/akash14n4rkmz64rn0tey0r5g07l8q5x0fh2h4hu44kt/1790911986959/1/1"
            ).json()["data"]
            assert failed_order["gpu_model"] == "p40"
            assert failed_order["bid_count"] == 0
            assert failed_order["winner"] is None
            assert failed_order["leases"] == []
            assert any(
                event["kind"] == "order_closed"
                for event in failed_order["provenance"]["lifecycle"]
            )
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
