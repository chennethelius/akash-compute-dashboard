"""Small, cron-friendly jobs. Run one index worker per checkpoint stream."""
import argparse
from datetime import datetime, timezone
import os

import httpx
from sqlalchemy import text
from compute_market.db.models import RawBlock, RawSnapshot, Checkpoint, Provider, CapacitySnapshot, JobRun
from compute_market.db.session import SessionLocal
from compute_market.ingestion.chain.client import ChainClient
from compute_market.ingestion.inventory.client import fetch_inventory, provider_capacity


def now():
    return datetime.now(timezone.utc)


def archive_chain(rpc_url: str, chain_id: str, start: int, end: int | None = None) -> int:
    if start < 1 or (end is not None and end < start):
        raise ValueError("Expected positive ordered height range")
    name = f"chain:{chain_id}:{start}"
    count = 0
    with httpx.Client(timeout=30) as http:
        rpc = ChainClient(rpc_url, http)
        stop = end if end is not None else rpc.latest_height()
        while True:
            with SessionLocal.begin() as session:
                # Serialize checkpoint writers. An interrupted transaction advances nothing.
                if session.bind.dialect.name == "postgresql":
                    session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:name))"), {"name": f"chain:{chain_id}"})
                checkpoint = session.get(Checkpoint, name)
                height = checkpoint.height + 1 if checkpoint else start
                if height > stop:
                    break
                existing = session.get(RawBlock, (chain_id, height))
                if existing is None:
                    block, results = rpc.block_pair(chain_id, height)
                    timestamp = datetime.fromisoformat(block["result"]["block"]["header"]["time"].replace("Z", "+00:00"))
                    session.add(RawBlock(chain_id=chain_id, height=height, timestamp=timestamp, block_payload=block, results_payload=results))
                if checkpoint is None:
                    session.add(Checkpoint(name=name, height=height, updated_at=now()))
                else:
                    checkpoint.height = height
                    checkpoint.updated_at = now()
                count += 1
    return count


def snapshot_inventory(base_url: str) -> int:
    with httpx.Client(timeout=30) as http:
        payload = fetch_inventory(base_url, http)
    collected_at = now()
    source = f"{base_url.rstrip('/')}/v1/providers"
    # Keep evidence even if a future API schema fails normalization.
    with SessionLocal.begin() as session:
        raw = RawSnapshot(collected_at=collected_at, source=source, payload=payload)
        session.add(raw)
        session.flush()
        raw_id = raw.id
    with SessionLocal.begin() as session:
        for record in payload:
            owner = record.get("owner")
            if not owner:
                raise ValueError("Missing provider owner")
            provider = session.get(Provider, owner)
            if provider is None:
                provider = Provider(id=owner, first_seen_at=collected_at, last_seen_at=collected_at)
                session.add(provider)
                session.flush()
            else:
                provider.last_seen_at = collected_at
            provider.name = record.get("name")
            provider.region = record.get("ipRegion")
            provider.attributes = {
                "reported_attributes": record.get("attributes", []),
                "gpu_models": record.get("gpuModels", []),
                "location": {key: record.get(key) for key in ("ipRegion", "ipRegionCode", "ipCountry", "ipCountryCode", "country", "city")},
                "region_source": "console.ipRegion",
            }
            capacity = provider_capacity(record)
            if capacity is not None:
                session.add(CapacitySnapshot(collected_at=collected_at, source=source, raw_snapshot_id=raw_id, **capacity))
    return len(payload)


def main():
    parser = argparse.ArgumentParser(description="Akash evidence collection; market decoding is pending")
    commands = parser.add_subparsers(dest="command", required=True)
    chain = commands.add_parser("chain")
    chain.add_argument("--rpc-url", default=os.getenv("AKASH_RPC_URL"))
    chain.add_argument("--chain-id", default=os.getenv("AKASH_CHAIN_ID", "akashnet-2"))
    chain.add_argument("--start-height", type=int, required=True)
    chain.add_argument("--end-height", type=int)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("--base-url", default=os.getenv("AKASH_CONSOLE_URL", "https://console-api.akash.network"))
    hourly = commands.add_parser("hourly")
    hourly.add_argument("--hour", required=True, help="UTC hour, e.g. 2026-10-01T12:00:00+00:00")
    args = parser.parse_args()
    if args.command == "chain" and not args.rpc_url:
        parser.error("--rpc-url or AKASH_RPC_URL is required; choose a node retaining the requested history")
    with SessionLocal.begin() as session:
        run = JobRun(job_name=args.command, started_at=now(), status="running", records_processed=0)
        session.add(run)
        session.flush()
        run_id = run.id
    try:
        count = execute(args, parser)
    except Exception as exc:
        with SessionLocal.begin() as session:
            run = session.get(JobRun, run_id)
            run.status = "failed"
            run.finished_at = now()
            run.error = str(exc)[:2000]
        raise
    with SessionLocal.begin() as session:
        run = session.get(JobRun, run_id)
        run.status = "completed"
        run.finished_at = now()
        run.records_processed = count


def execute(args, parser):
    if args.command == "chain":
        count = archive_chain(args.rpc_url, args.chain_id, args.start_height, args.end_height)
    elif args.command == "inventory":
        count = snapshot_inventory(args.base_url)
    else:
        from compute_market.jobs.hourly import aggregate_capacity_hour
        print(aggregate_capacity_hour(datetime.fromisoformat(args.hour)))
        return 1
    print(f"Processed {count} records. Chain archive is raw-only; normalized marketplace decoding is not implemented.")
    return count


if __name__ == "__main__":
    main()
