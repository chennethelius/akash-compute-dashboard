"""Normalized contracts. Native prices are decimal; missing USD conversions remain null."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, Numeric
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc)


def identifier():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class RawBlock(Base):
    __tablename__ = "raw_blocks"
    chain_id: Mapped[str] = mapped_column(primary_key=True)
    height: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    block_payload: Mapped[dict] = mapped_column(JSON)
    results_payload: Mapped[dict] = mapped_column(JSON)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    decoder_version: Mapped[str] = mapped_column(default="raw-v1")


class RawSnapshot(Base):
    __tablename__ = "raw_snapshots"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    # Which source records the payload kept; "all" is the complete response.
    retention_policy: Mapped[str] = mapped_column(default="all", server_default="all")
    source_record_count: Mapped[int | None]
    retained_record_count: Mapped[int | None]


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    name: Mapped[str] = mapped_column(primary_key=True)
    height: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    job_name: Mapped[str]
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(default="running")
    error: Mapped[str | None]
    records_processed: Mapped[int] = mapped_column(default=0)


class Provider(Base):
    __tablename__ = "providers"
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str | None]
    region: Mapped[str | None]
    created_height: Mapped[int | None] = mapped_column(BigInteger)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(primary_key=True)
    chain_id: Mapped[str] = mapped_column(default="akashnet-2")
    owner: Mapped[str]
    dseq: Mapped[str]
    gseq: Mapped[int]
    oseq: Mapped[int]
    created_height: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    gpu_model: Mapped[str | None] = mapped_column(index=True)
    gpu_count: Mapped[int | None]
    cpu_units: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    memory_bytes: Mapped[int | None] = mapped_column(BigInteger)
    storage_bytes: Mapped[int | None] = mapped_column(BigInteger)
    region: Mapped[str | None]
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)


class Bid(Base):
    __tablename__ = "bids"
    id: Mapped[str] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), index=True)
    created_height: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    price_amount: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    price_denom: Mapped[str]
    price_usd_normalized: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    state: Mapped[str]
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)


class Lease(Base):
    __tablename__ = "leases"
    id: Mapped[str] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), index=True)
    created_height: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    winning_bid_price: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    price_denom: Mapped[str]
    price_usd_normalized: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)


class CapacitySnapshot(Base):
    __tablename__ = "provider_gpu_snapshots"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    gpu_model: Mapped[str | None]
    active: Mapped[int | None]
    available: Mapped[int | None]
    pending: Mapped[int | None]
    total: Mapped[int | None]
    source: Mapped[str]
    scope: Mapped[str] = mapped_column(default="provider")
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_online: Mapped[bool | None]
    raw_snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("raw_snapshots.id"))


ProviderGpuSnapshot = CapacitySnapshot


class MarketMetricHourly(Base):
    __tablename__ = "market_metrics_hourly"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    gpu_model: Mapped[str | None]
    region: Mapped[str | None]
    definition_version: Mapped[str] = mapped_column(default="v1")
    metrics: Mapped[dict] = mapped_column(JSON)


class MarketplaceEvent(Base):
    __tablename__ = "marketplace_events"
    id: Mapped[str] = mapped_column(primary_key=True)
    chain_id: Mapped[str]
    height: Mapped[int] = mapped_column(BigInteger, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event_type: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    decoder_version: Mapped[str]


class BlockProjection(Base):
    """Per-block coverage, separate from successful archival."""

    __tablename__ = "block_projections"
    chain_id: Mapped[str] = mapped_column(primary_key=True)
    height: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    decoder_version: Mapped[str] = mapped_column(primary_key=True)
    status: Mapped[str]
    event_count: Mapped[int]
    issues: Mapped[list] = mapped_column(JSON, default=list)
    projected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
