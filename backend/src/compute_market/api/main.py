"""Read API. Real mode never substitutes synthetic observations on failure."""

import csv
import io
import os
from datetime import datetime, timedelta, timezone
from statistics import median

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from compute_market.db.models import (
    Bid,
    BlockProjection,
    CapacitySnapshot,
    Checkpoint,
    Lease,
    MarketMetricHourly,
    Order,
    Provider,
    RawBlock,
    RawSnapshot,
)
from compute_market.db.session import get_session
from . import demo

app = FastAPI(title="Compute Market Research API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)


def is_demo():
    return os.getenv("DEMO_MODE", "false").lower() == "true"


def envelope(data):
    return {
        "meta": {
            "mode": "demo" if is_demo() else "live",
            "label": "Synthetic demonstration data"
            if is_demo()
            else "Observed data; coverage may be incomplete",
            "as_of": demo.ANCHOR.isoformat()
            if is_demo()
            else datetime.now(timezone.utc).isoformat(),
            "coverage_note": "Synthetic fixtures cannot support research conclusions."
            if is_demo()
            else "USD prices require validated conversion. Raw ingestion is not equivalent to normalized coverage.",
        },
        "data": data,
    }


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database unavailable or migrations missing. No synthetic fallback was used."
        },
    )


def filters(
    gpu_model: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    region: str | None = None,
):
    for key, value in (("start", start), ("end", end)):
        if value is not None and value.tzinfo is None:
            raise HTTPException(422, f"{key} must include a timezone")
    if start and end and start >= end:
        raise HTTPException(422, "start must precede end")
    return dict(gpu_model=gpu_model, start=start, end=end, region=region)


def matches(row, f, timestamp="created_at"):
    if f["gpu_model"] and row.get("gpu_model") != f["gpu_model"]:
        return False
    if f["region"] and row.get("region") != f["region"]:
        return False
    value = row.get(timestamp)
    if value:
        dt = (
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            if isinstance(value, str)
            else value
        )
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if f["start"] and dt < f["start"]:
            return False
        if f["end"] and dt >= f["end"]:
            return False
    return True


def order_query(f):
    query = select(Order)
    for name in ("gpu_model", "region"):
        if f[name]:
            query = query.where(getattr(Order, name) == f[name])
    if f["start"]:
        query = query.where(Order.created_at >= f["start"])
    if f["end"]:
        query = query.where(Order.created_at < f["end"])
    return query.order_by(Order.created_at.desc(), Order.id)


def event_position(row):
    """Order within a block when evidence provides execution coordinates."""
    provenance = row.provenance or {}
    phase = provenance.get("phase", "transaction")
    phase_order = 0 if phase == "begin_block" else 1 if phase == "transaction" else 2
    return (
        row.created_height,
        phase_order,
        provenance.get("tx_index") or 0,
        provenance.get("event_index") or 0,
    )


def utc_timestamp(value):
    # SQLite preview storage loses tzinfo; all ingested timestamps are UTC.
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def serialize_order(row, session):
    bids = session.scalars(
        select(Bid).where(Bid.order_id == row.id).order_by(Bid.created_height, Bid.id)
    ).all()
    leases = session.scalars(
        select(Lease)
        .where(Lease.order_id == row.id)
        .order_by(Lease.created_height, Lease.id)
    ).all()
    # Use only bids recorded before the first selection when it exists.
    selection = min((event_position(lease) for lease in leases), default=None)
    eligible = [
        bid for bid in bids if selection is None or event_position(bid) <= selection
    ]
    prices = [
        float(b.price_usd_normalized)
        for b in eligible
        if b.price_usd_normalized is not None
    ]
    winners = {lease.provider_id for lease in leases}
    selected_bid_ids = {
        lease.provenance.get("bid_id")
        for lease in leases
        if lease.provenance.get("bid_id")
    }
    return dict(
        id=row.id,
        created_height=row.created_height,
        created_at=utc_timestamp(row.created_at),
        gpu_model=row.gpu_model,
        gpu_count=row.gpu_count,
        cpu_units=row.cpu_units,
        memory_bytes=row.memory_bytes,
        storage_bytes=row.storage_bytes,
        region=row.region,
        bid_count=len({b.provider_id for b in eligible}),
        lowest_bid=min(prices) if prices else None,
        median_bid=median(prices) if prices else None,
        highest_bid=max(prices) if prices else None,
        winner=next(iter(winners)) if len(winners) == 1 else None,
        bids=[
            dict(
                id=b.id,
                provider_id=b.provider_id,
                provider_name=b.provider_id,
                price=float(b.price_usd_normalized)
                if b.price_usd_normalized is not None
                else None,
                native_price=b.provenance.get("native_price", str(b.price_amount)),
                denom=b.price_denom,
                created_height=b.created_height,
                created_at=utc_timestamp(b.created_at),
                state=b.state,
                is_winner=b.id in selected_bid_ids
                if selected_bid_ids
                else b.provider_id in winners,
                provenance=b.provenance,
            )
            for b in bids
        ],
        leases=[
            dict(
                id=lease.id,
                provider_id=lease.provider_id,
                created_height=lease.created_height,
                created_at=utc_timestamp(lease.created_at),
                closed_at=utc_timestamp(lease.closed_at),
                winning_bid_price=lease.provenance.get(
                    "native_price", str(lease.winning_bid_price)
                ),
                price_denom=lease.price_denom,
                provenance=lease.provenance,
            )
            for lease in leases
        ],
        market_at_order=dict(
            utilization=None,
            available_gpus=None,
            active_providers=None,
            provider_hhi=None,
        ),
        attributes=row.attributes,
        provenance=row.provenance,
    )


@app.get("/health")
def health():
    return {"status": "ok", "mode": "demo" if is_demo() else "live"}


@app.get("/ready")
def ready(session: Session = Depends(get_session)):
    # A successful process health check does not imply a usable database.
    for model in (Order, RawBlock, CapacitySnapshot, BlockProjection):
        session.execute(select(model).limit(0))
    return {"status": "ready", "database": "reachable", "core_tables": "available"}


@app.get("/v1/coverage")
def coverage(session: Session = Depends(get_session)):
    if is_demo():
        return envelope(
            {
                "raw_blocks": 0,
                "normalized_orders": 0,
                "checkpoints": [],
                "synthetic": True,
            }
        )
    checkpoints = session.scalars(select(Checkpoint)).all()
    return envelope(
        dict(
            raw_blocks=session.scalar(select(func.count()).select_from(RawBlock)),
            normalized_orders=session.scalar(select(func.count()).select_from(Order)),
            raw_snapshots=session.scalar(select(func.count()).select_from(RawSnapshot)),
            decoding=[
                dict(status=status, blocks=count)
                for status, count in session.execute(
                    select(BlockProjection.status, func.count()).group_by(
                        BlockProjection.status
                    )
                )
            ],
            checkpoints=[
                dict(name=c.name, height=c.height, updated_at=c.updated_at)
                for c in checkpoints
            ],
        )
    )


@app.get("/v1/orders")
def orders(
    f: dict = Depends(filters),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    if is_demo():
        return envelope(
            [o for o in reversed(demo.ORDERS) if matches(o, f)][offset : offset + limit]
        )
    return envelope(
        [
            serialize_order(o, session)
            for o in session.scalars(order_query(f).offset(offset).limit(limit))
        ]
    )


@app.get("/v1/orders/{order_id:path}")
def order_detail(order_id: str, session: Session = Depends(get_session)):
    if is_demo():
        row = next((o for o in demo.ORDERS if o["id"] == order_id), None)
    else:
        model = session.get(Order, order_id)
        row = serialize_order(model, session) if model else None
    if row is None:
        raise HTTPException(404, "Order not found")
    return envelope(row)


@app.get("/v1/providers")
def providers(f: dict = Depends(filters), session: Session = Depends(get_session)):
    if is_demo():
        return envelope(
            [p for p in demo.PROVIDERS if matches(p, f, timestamp="last_seen_at")]
        )
    rows = session.scalars(select(Provider).order_by(Provider.id)).all()
    result = []
    for p in rows:
        if f["region"] and p.region != f["region"]:
            continue
        snapshots = select(CapacitySnapshot).where(CapacitySnapshot.provider_id == p.id)
        if f["gpu_model"]:
            snapshots = snapshots.where(CapacitySnapshot.gpu_model == f["gpu_model"])
        if f["start"]:
            snapshots = snapshots.where(CapacitySnapshot.collected_at >= f["start"])
        if f["end"]:
            snapshots = snapshots.where(CapacitySnapshot.collected_at < f["end"])
        snap = session.scalar(
            snapshots.order_by(CapacitySnapshot.collected_at.desc()).limit(1)
        )
        if f["gpu_model"] and not snap:
            continue
        result.append(
            dict(
                id=p.id,
                name=p.name or p.id,
                region=p.region,
                gpu_model=snap.gpu_model if snap else None,
                active_gpus=snap.active if snap else None,
                available_gpus=snap.available if snap else None,
                total_gpus=snap.total if snap else None,
                wins=None,
                bid_count=None,
                average_bid=None,
                average_winning_price=None,
                win_rate=None,
                market_share=None,
                first_seen_at=p.first_seen_at,
                last_seen_at=p.last_seen_at,
            )
        )
    return envelope(result)


@app.get("/v1/providers/{provider_id}")
def provider_detail(provider_id: str, session: Session = Depends(get_session)):
    result = providers(dict(gpu_model=None, start=None, end=None, region=None), session)
    row = next((p for p in result["data"] if p["id"] == provider_id), None)
    if row is None:
        raise HTTPException(404, "Provider not found")
    return envelope(row)


@app.get("/v1/market/timeseries")
def timeseries(f: dict = Depends(filters), session: Session = Depends(get_session)):
    if is_demo():
        return envelope([r for r in demo.TIMESERIES if matches(r, f, "timestamp")])
    query = select(MarketMetricHourly).order_by(MarketMetricHourly.timestamp)
    if f["gpu_model"]:
        query = query.where(MarketMetricHourly.gpu_model == f["gpu_model"])
    else:
        query = query.where(MarketMetricHourly.gpu_model.is_(None))
    if f["region"]:
        query = query.where(MarketMetricHourly.region == f["region"])
    else:
        query = query.where(MarketMetricHourly.region.is_(None))
    if f["start"]:
        query = query.where(MarketMetricHourly.timestamp >= f["start"])
    if f["end"]:
        query = query.where(MarketMetricHourly.timestamp < f["end"])
    return envelope(
        [
            dict(**r.metrics, timestamp=r.timestamp, gpu_model=r.gpu_model)
            for r in session.scalars(query)
        ]
    )


@app.get("/v1/market/summary")
def summary(f: dict = Depends(filters), session: Session = Depends(get_session)):
    keys = "active_gpus available_gpus total_gpus utilization active_providers orders_24h leases_24h median_winning_price median_bidders_per_order provider_hhi".split()
    result = dict.fromkeys(keys)
    series = timeseries(f, session)["data"]
    if series:
        last = series[-1]
        for key in (
            "active_gpus",
            "available_gpus",
            "total_gpus",
            "utilization",
            "provider_hhi",
        ):
            result[key] = last.get(key)
        result["median_winning_price"] = last.get("median_price")
        result["active_providers"] = last.get("active_provider_count")
    if is_demo():
        selected = [o for o in demo.ORDERS if matches(o, f)]
        recent = [
            o
            for o in selected
            if datetime.fromisoformat(o["created_at"])
            > demo.ANCHOR - timedelta(hours=24)
        ]
        result.update(
            orders_24h=len(recent),
            leases_24h=len(recent),
            median_bidders_per_order=median([o["bid_count"] for o in selected])
            if selected
            else None,
            active_providers=len({o["winner"] for o in selected}),
        )
    return envelope(result)


@app.get("/v1/research/observations")
def observations(f: dict = Depends(filters)):
    # No unvalidated joins or research features are fabricated in live mode.
    return envelope(
        [o for o in demo.OBSERVATIONS if matches(o, f, "timestamp")]
        if is_demo()
        else []
    )


@app.get("/v1/exports/orders.csv")
def export_orders(f: dict = Depends(filters), session: Session = Depends(get_session)):
    fields = "id created_at gpu_model gpu_count cpu_units memory_bytes storage_bytes bid_count lowest_bid median_bid highest_bid winner region".split()
    output = io.StringIO()
    writer = csv.DictWriter(
        output, fieldnames=["data_mode"] + fields, extrasaction="ignore"
    )
    writer.writeheader()
    rows = (
        [o for o in demo.ORDERS if matches(o, f)]
        if is_demo()
        else (
            serialize_order(o, session)
            for o in session.scalars(order_query(f)).yield_per(500)
        )
    )
    for row in rows:
        safe = {
            k: (
                "'" + v
                if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r"))
                else v
            )
            for k, v in row.items()
        }
        writer.writerow(dict(safe, data_mode="synthetic" if is_demo() else "live"))
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="orders.csv"'},
    )
