"""Long-running inventory collector; no automatic chain backfill."""

import logging
import os
import signal
import threading
from datetime import datetime, timedelta, timezone

from compute_market.db.models import JobRun
from compute_market.db.session import SessionLocal
from compute_market.jobs.cli import snapshot_inventory
from compute_market.jobs.hourly import aggregate_capacity_hour

logger = logging.getLogger(__name__)


def collect_once(base_url: str) -> None:
    with SessionLocal.begin() as session:
        run = JobRun(
            job_name="inventory-worker",
            started_at=datetime.now(timezone.utc),
            status="running",
            records_processed=0,
        )
        session.add(run)
        session.flush()
        run_id = run.id
    try:
        count = snapshot_inventory(base_url)
        hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        aggregate_capacity_hour(hour - timedelta(hours=1))
        # The current hour is provisional and is recomputed each successful cycle.
        aggregate_capacity_hour(hour)
    except Exception as exc:
        with SessionLocal.begin() as session:
            run = session.get(JobRun, run_id)
            run.status = "failed"
            run.finished_at = datetime.now(timezone.utc)
            run.error = str(exc)[:2000]
        raise
    with SessionLocal.begin() as session:
        run = session.get(JobRun, run_id)
        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.records_processed = count


def run_worker(base_url: str, interval_seconds: int, stop: threading.Event) -> None:
    if interval_seconds < 30:
        raise ValueError("SNAPSHOT_INTERVAL_SECONDS must be at least 30")
    while not stop.is_set():
        try:
            collect_once(base_url)
            logger.info("Inventory collected and capacity metrics refreshed")
        except Exception:
            logger.exception(
                "Collection cycle failed; retrying after %s seconds", interval_seconds
            )
        # Event.wait allows SIGTERM to interrupt scheduling, unlike time.sleep.
        stop.wait(interval_seconds)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    stop = threading.Event()

    def request_stop(signum, frame):
        logger.info("Shutdown requested; finishing the current cycle")
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    run_worker(
        os.getenv("AKASH_CONSOLE_URL", "https://console-api.akash.network"),
        int(os.getenv("SNAPSHOT_INTERVAL_SECONDS", "600")),
        stop,
    )


if __name__ == "__main__":
    main()
