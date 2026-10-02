"""Conservative projections of validated marketplace actions.

Actions are ordered source events, not current-state API observations. Missing
antecedents produce coverage issues instead of invented orders or winning bids.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from compute_market.db.models import Bid, Lease, MarketplaceEvent, Order, Provider


def order_id(chain_id: str, value: dict) -> str:
    return "/".join(
        [
            chain_id,
            value["owner"],
            str(value["dseq"]),
            str(value["gseq"]),
            str(value["oseq"]),
        ]
    )


def bid_id(chain_id: str, value: dict) -> str:
    return f"{order_id(chain_id, value)}/{value['provider']}/{value.get('bseq', 0)}"


def instant(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def evidence(action: dict, version: str) -> dict:
    return {
        "decoder_version": version,
        "height": action["height"],
        "timestamp": action["timestamp"],
        "tx_hash": action.get("tx_hash"),
        "tx_index": action.get("tx_index"),
        "event_index": action.get("event_index"),
        "msg_index": action.get("msg_index"),
        "phase": action.get("phase", "transaction"),
        "event_id": action["event_id"],
        "source_event": action["payload"].get("raw_event"),
    }


def append_lifecycle(row, action: dict, version: str):
    provenance = dict(row.provenance or {})
    lifecycle = list(provenance.get("lifecycle", []))
    if not any(item["event_id"] == action["event_id"] for item in lifecycle):
        lifecycle.append(
            {
                **evidence(action, version),
                "kind": action["kind"],
                "timestamp": instant(action["timestamp"]).isoformat(),
            }
        )
    row.provenance = {**provenance, "lifecycle": lifecycle}


def ensure_provider(session: Session, address: str, timestamp):
    provider = session.get(Provider, address)
    timestamp = instant(timestamp)
    if provider is None:
        provider = Provider(id=address, first_seen_at=timestamp, last_seen_at=timestamp)
        session.add(provider)
        session.flush()
    else:
        provider.first_seen_at = min(instant(provider.first_seen_at), timestamp)
        provider.last_seen_at = max(instant(provider.last_seen_at), timestamp)


def project_actions(
    session: Session, chain_id: str, actions: list[dict], version: str
) -> list[dict]:
    issues = []
    for action in actions:
        payload = action["payload"]
        identity = payload.get("id", {})
        stamp = instant(action["timestamp"])
        event = session.get(MarketplaceEvent, action["event_id"])
        if event is None:
            session.add(
                MarketplaceEvent(
                    id=action["event_id"],
                    chain_id=chain_id,
                    height=action["height"],
                    timestamp=stamp,
                    event_type=action["kind"],
                    payload=action,
                    decoder_version=version,
                )
            )
            session.flush()
        elif event.payload != action:
            raise ValueError(f"Conflicting event evidence: {action['event_id']}")
        kind = action["kind"]
        provenance = evidence(action, version)
        if kind == "order_created":
            oid = order_id(chain_id, identity)
            row = session.get(Order, oid)
            if row is None:
                resources = payload.get("resources") or {}
                session.add(
                    Order(
                        id=oid,
                        chain_id=chain_id,
                        owner=identity["owner"],
                        dseq=str(identity["dseq"]),
                        gseq=int(identity["gseq"]),
                        oseq=int(identity["oseq"]),
                        created_height=action["height"],
                        created_at=stamp,
                        gpu_model=resources.get("gpu_model"),
                        gpu_count=resources.get("gpu_count"),
                        cpu_units=resources.get("cpu_units"),
                        memory_bytes=resources.get("memory_bytes"),
                        storage_bytes=resources.get("storage_bytes"),
                        region=resources.get("region"),
                        attributes=resources.get("attributes", {}),
                        provenance=provenance,
                    )
                )
                session.flush()
            if not payload.get("resources"):
                issues.append(
                    {
                        "event_id": action["event_id"],
                        "reason": "order_resources_missing",
                    }
                )
        elif kind in {"bid_created", "lease_created"}:
            oid = order_id(chain_id, identity)
            if session.get(Order, oid) is None:
                issues.append(
                    {
                        "event_id": action["event_id"],
                        "reason": "order_not_in_indexed_history",
                        "order_id": oid,
                    }
                )
                continue
            ensure_provider(session, identity["provider"], stamp)
            key = bid_id(chain_id, identity)
            price = payload.get("price")
            if kind == "bid_created":
                if not price:
                    issues.append(
                        {"event_id": action["event_id"], "reason": "bid_price_missing"}
                    )
                    continue
                if session.get(Bid, key) is None:
                    session.add(
                        Bid(
                            id=key,
                            order_id=oid,
                            provider_id=identity["provider"],
                            created_height=action["height"],
                            created_at=stamp,
                            price_amount=Decimal(price["amount"]),
                            price_denom=price["denom"],
                            state="open",
                            provenance={**provenance, "native_price": price["amount"]},
                        )
                    )
                    session.flush()
            else:
                bid = session.get(Bid, key)
                if bid is None:
                    issues.append(
                        {
                            "event_id": action["event_id"],
                            "reason": "winning_bid_not_in_indexed_history",
                            "bid_id": key,
                        }
                    )
                    continue
                native = bid.provenance.get("native_price", str(bid.price_amount))
                if price and (
                    Decimal(price["amount"]) != Decimal(native)
                    or price["denom"] != bid.price_denom
                ):
                    raise ValueError(
                        "Lease price does not reconcile with the selected bid"
                    )
                if session.get(Lease, key) is None:
                    session.add(
                        Lease(
                            id=key,
                            order_id=oid,
                            provider_id=identity["provider"],
                            created_height=action["height"],
                            created_at=stamp,
                            winning_bid_price=Decimal(native),
                            price_denom=bid.price_denom,
                            provenance={
                                **provenance,
                                "native_price": native,
                                "bid_id": key,
                            },
                        )
                    )
                    session.flush()
                append_lifecycle(bid, action, version)
                if bid.state == "open":
                    bid.state = "active"
        elif kind == "deployment_created":
            # Retain deployment evidence; only an order event creates an order.
            continue
        elif kind in {
            "bid_closed",
            "lease_closed",
            "order_closed",
            "deployment_closed",
            "group_closed",
        }:
            if kind == "bid_closed":
                rows = [session.get(Bid, bid_id(chain_id, identity))]
            elif kind == "lease_closed":
                rows = [session.get(Lease, bid_id(chain_id, identity))]
            elif kind == "order_closed":
                rows = [session.get(Order, order_id(chain_id, identity))]
            else:
                query = select(Order).where(
                    Order.chain_id == chain_id,
                    Order.owner == identity["owner"],
                    Order.dseq == str(identity["dseq"]),
                )
                if kind == "group_closed":
                    query = query.where(Order.gseq == int(identity["gseq"]))
                rows = list(session.scalars(query))
            if not rows or any(row is None for row in rows):
                issues.append(
                    {
                        "event_id": action["event_id"],
                        "reason": "closed_entity_not_in_indexed_history",
                    }
                )
            for row in filter(None, rows):
                append_lifecycle(row, action, version)
                if isinstance(row, Bid):
                    row.state = "closed"
                if isinstance(row, Lease):
                    row.closed_at = (
                        min(instant(row.closed_at), stamp) if row.closed_at else stamp
                    )
        else:
            issues.append(
                {
                    "event_id": action["event_id"],
                    "reason": "projection_kind_unsupported",
                    "kind": kind,
                }
            )
    return issues
