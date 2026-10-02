"""Bounded chain collection; run separately from time-sensitive inventory jobs."""

import logging
import os
import signal
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from compute_market.db.models import Checkpoint, JobRun
from compute_market.db.session import SessionLocal
from compute_market.ingestion.chain.client import ChainClient
from compute_market.ingestion.chain.decoder import DECODER_VERSION
from compute_market.jobs.cli import archive_chain
from compute_market.jobs.decode import decode_archived

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChainConfig:
    rpc_url: str
    chain_id: str
    start_height: int
    batch_size: int = 20
    interval_seconds: int = 30
    max_retry_seconds: int = 300

    def __post_init__(self):
        if not self.rpc_url or not self.chain_id or self.start_height < 1:
            raise ValueError("RPC URL, chain ID and positive start height are required")
        if not 1 <= self.batch_size <= 100:
            raise ValueError("CHAIN_BATCH_SIZE must be between 1 and 100")
        if self.interval_seconds < 5 or self.max_retry_seconds < self.interval_seconds:
            raise ValueError("Poll interval must be >=5 and retry cap >= poll interval")

    @property
    def checkpoint_name(self):
        return f"projection:{self.chain_id}:{self.start_height}:{DECODER_VERSION}"


def collect_batch(config: ChainConfig) -> dict:
    with SessionLocal.begin() as session:
        run = JobRun(
            job_name="chain-worker",
            started_at=datetime.now(timezone.utc),
            status="running",
            records_processed=0,
        )
        session.add(run)
        session.flush()
        run_id = run.id
    try:
        with SessionLocal() as session:
            checkpoint = session.get(Checkpoint, config.checkpoint_name)
            start = checkpoint.height + 1 if checkpoint else config.start_height
        with httpx.Client(timeout=30) as http:
            tip = ChainClient(config.rpc_url, http).latest_height()
        if tip < start - 1:
            raise ValueError("RPC tip is behind the projection checkpoint")
        end = min(tip, start + config.batch_size - 1)
        result = {"complete_blocks": 0, "partial_blocks": 0, "actions": 0}
        if end >= start:
            # Stable original start preserves the archival checkpoint on restart.
            archive_chain(config.rpc_url, config.chain_id, config.start_height, end)
            result = decode_archived(
                config.chain_id, start, end, checkpoint_name=config.checkpoint_name
            )
    except Exception as exc:
        with SessionLocal.begin() as session:
            run = session.get(JobRun, run_id)
            run.status = "failed"
            run.finished_at = datetime.now(timezone.utc)
            # HTTP/DB exceptions may contain credential-bearing URLs.
            run.error = f"{type(exc).__name__}: collection failed; checkpoints retained"
        raise
    with SessionLocal.begin() as session:
        run = session.get(JobRun, run_id)
        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.records_processed = result["complete_blocks"] + result["partial_blocks"]
    return {**result, "tip": tip, "end_height": end, "start_height": start}


def run_worker(config: ChainConfig, stop: threading.Event):
    delay = config.interval_seconds
    while not stop.is_set():
        failed = False
        try:
            result = collect_batch(config)
            logger.info("Chain batch: %s", result)
            delay = config.interval_seconds
        except Exception as exc:
            failed = True
            logger.error(
                "Chain batch failed (%s); retry in %ss", type(exc).__name__, delay
            )
        stop.wait(delay)
        if failed:
            delay = min(delay * 2, config.max_retry_seconds)


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    config = ChainConfig(
        rpc_url=os.getenv("AKASH_RPC_URL", ""),
        chain_id=os.getenv("AKASH_CHAIN_ID", "akashnet-2"),
        start_height=int(os.getenv("CHAIN_START_HEIGHT", "0")),
        batch_size=int(os.getenv("CHAIN_BATCH_SIZE", "20")),
        interval_seconds=int(os.getenv("CHAIN_POLL_SECONDS", "30")),
        max_retry_seconds=int(os.getenv("CHAIN_MAX_RETRY_SECONDS", "300")),
    )
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    run_worker(config, stop)


if __name__ == "__main__":
    main()
