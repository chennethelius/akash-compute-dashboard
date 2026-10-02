from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from compute_market.db.models import Base, BlockProjection, Checkpoint, JobRun, RawBlock
from compute_market.jobs import chain_worker, cli, decode


@pytest.fixture
def setup_worker(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    for module in (chain_worker, cli, decode):
        monkeypatch.setattr(module, "SessionLocal", sessions)
    monkeypatch.setattr(chain_worker.ChainClient, "latest_height", lambda self: 3)
    calls = []

    def pair(self, chain_id, height):
        calls.append(height)
        return (
            {
                "result": {
                    "block": {
                        "header": {
                            "time": "2026-01-01T00:00:00Z",
                            "chain_id": chain_id,
                            "height": str(height),
                        },
                        "data": {"txs": []},
                    }
                }
            },
            {"result": {"height": str(height), "txs_results": []}},
        )

    monkeypatch.setattr(cli.ChainClient, "block_pair", pair)
    yield (
        sessions,
        calls,
        chain_worker.ChainConfig("https://rpc.test", "test", 1, batch_size=2),
    )
    engine.dispose()


def test_bounded_batches_resume_and_idle_without_duplicate_blocks(setup_worker):
    sessions, calls, config = setup_worker
    assert chain_worker.collect_batch(config)["end_height"] == 2
    assert chain_worker.collect_batch(config)["end_height"] == 3
    assert chain_worker.collect_batch(config)["complete_blocks"] == 0
    assert calls == [1, 2, 3]
    with sessions() as session:
        assert session.get(Checkpoint, "chain:test:1").height == 3
        assert session.get(Checkpoint, config.checkpoint_name).height == 3
        assert session.scalar(select(func.count()).select_from(RawBlock)) == 3
        assert session.scalar(select(func.count()).select_from(BlockProjection)) == 3


def test_decode_crash_retains_raw_and_resumes_failed_height(setup_worker, monkeypatch):
    from compute_market.ingestion.chain import decoder

    sessions, calls, config = setup_worker
    original = decoder.decode_block

    def fail(chain_id, height, *args):
        if height == 2:
            raise ValueError("credential-like-detail-must-not-be-persisted")
        return original(chain_id, height, *args)

    monkeypatch.setattr(decoder, "decode_block", fail)
    with pytest.raises(ValueError):
        chain_worker.collect_batch(config)
    with sessions() as session:
        assert session.get(Checkpoint, "chain:test:1").height == 2
        assert session.get(Checkpoint, config.checkpoint_name).height == 1
        run = session.scalar(select(JobRun))
        assert run.status == "failed"
        assert "credential-like" not in run.error
    monkeypatch.setattr(decoder, "decode_block", original)
    chain_worker.collect_batch(config)
    assert calls == [1, 2, 3]
    with sessions() as session:
        assert session.get(Checkpoint, config.checkpoint_name).height == 3


def test_partial_decoding_is_recorded_not_reported_complete(setup_worker, monkeypatch):
    from compute_market.ingestion.chain import decoder

    sessions, _, config = setup_worker
    monkeypatch.setattr(
        decoder,
        "decode_block",
        lambda *args: {
            "status": "partial",
            "actions": [],
            "issues": [{"reason": "unsupported_version"}],
        },
    )
    result = chain_worker.collect_batch(config)
    assert result["partial_blocks"] == 2
    assert result["complete_blocks"] == 0
    with sessions() as session:
        assert session.get(Checkpoint, config.checkpoint_name).height == 2
        assert all(
            row.status == "partial" for row in session.scalars(select(BlockProjection))
        )


def test_projection_checkpoint_rejects_gap(setup_worker):
    sessions, _, config = setup_worker
    with sessions.begin() as session:
        session.add(
            Checkpoint(
                name=config.checkpoint_name,
                height=1,
                updated_at=datetime.now(timezone.utc),
            )
        )
    with pytest.raises(ValueError, match="cannot skip"):
        decode.decode_archived("test", 3, 3, checkpoint_name=config.checkpoint_name)


def test_retry_backoff_is_capped_and_resets_after_success(monkeypatch):
    calls = []
    attempts = iter([False, False, False, True, False])

    def collect(config):
        if not next(attempts):
            raise RuntimeError("temporary outage")
        return {}

    class Stop:
        def is_set(self):
            return len(calls) == 5

        def wait(self, seconds):
            calls.append(seconds)

    monkeypatch.setattr(chain_worker, "collect_batch", collect)
    config = chain_worker.ChainConfig(
        "https://rpc.test", "test", 1, interval_seconds=5, max_retry_seconds=15
    )
    chain_worker.run_worker(config, Stop())
    assert calls == [5, 10, 15, 5, 5]


def test_provider_url_keeps_tls_and_escaped_credentials():
    from compute_market.db.config import database_url

    url = database_url("postgresql://user:p%40ss%25@db.example/test?sslmode=require")
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ss%"
    assert url.query["sslmode"] == "require"
    assert database_url("sqlite:///sample.db").drivername == "sqlite"
