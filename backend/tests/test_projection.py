from copy import deepcopy

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from compute_market.db.models import Base, Bid, Lease, MarketplaceEvent, Order
from compute_market.ingestion.chain.projector import project_actions


@pytest.fixture
def sessions():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield sessionmaker(engine)
    engine.dispose()


def actions():
    identity = dict(owner="tenant", dseq="1", gseq=1, oseq=1)

    def item(kind, height, payload):
        return dict(
            event_id=f"test/{height}/0/0",
            kind=kind,
            height=height,
            timestamp=f"2026-01-01T00:00:{height:02d}+00:00",
            tx_hash=f"tx{height}",
            tx_index=0,
            event_index=0,
            payload=payload,
        )

    order = item(
        "order_created",
        1,
        {
            "id": identity,
            "resources": {"gpu_count": 1, "gpu_model": "H100", "attributes": {}},
        },
    )
    cheap = item(
        "bid_created",
        2,
        {
            "id": dict(identity, provider="cheap", bseq=0),
            "price": {"amount": "1.000000000000000001", "denom": "uact"},
        },
    )
    winner = item(
        "bid_created",
        3,
        {
            "id": dict(identity, provider="selected", bseq=1),
            "price": {"amount": "2.000000000000000002", "denom": "uact"},
        },
    )
    lease = item(
        "lease_created",
        4,
        {"id": winner["payload"]["id"], "price": winner["payload"]["price"]},
    )
    close = item("lease_closed", 5, {"id": winner["payload"]["id"]})
    return [order, cheap, winner, lease, close]


def test_replay_preserves_actual_winner_precise_evidence_and_closure(sessions):
    source = actions()
    for _ in range(2):
        with sessions.begin() as session:
            assert project_actions(session, "test", source, "v1") == []
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 1
        assert session.scalar(select(func.count()).select_from(Bid)) == 2
        assert session.scalar(select(func.count()).select_from(MarketplaceEvent)) == 5
        lease = session.scalar(select(Lease))
        assert lease.provider_id == "selected"
        assert lease.id.endswith("selected/1")
        assert lease.closed_at.second == 5
        assert lease.provenance["native_price"] == "2.000000000000000002"
        assert len(lease.provenance["lifecycle"]) == 1


def test_missing_history_stays_explicit_and_reconciles_after_replay(sessions):
    source = actions()
    with sessions.begin() as session:
        issues = project_actions(session, "test", source[3:], "v1")
        assert {x["reason"] for x in issues} == {
            "order_not_in_indexed_history",
            "closed_entity_not_in_indexed_history",
        }
        assert session.scalar(select(func.count()).select_from(Lease)) == 0
    with sessions.begin() as session:
        assert project_actions(session, "test", source, "v1") == []


def test_conflicting_lease_price_rolls_back(sessions):
    source = deepcopy(actions())
    source[3]["payload"]["price"] = {"amount": "99", "denom": "uact"}
    with pytest.raises(ValueError, match="does not reconcile"):
        with sessions.begin() as session:
            project_actions(session, "test", source, "v1")
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 0
