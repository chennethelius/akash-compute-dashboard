"""Opt-in PostgreSQL smoke test, isolated in a unique temporary schema."""

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from compute_market.db.models import (
    CapacitySnapshot,
    Checkpoint,
    MarketMetricHourly,
    Provider,
    RawBlock,
)
from compute_market.jobs import cli, hourly


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not configured"
)
def test_postgres_migration_archive_and_hourly_idempotency(monkeypatch):
    url = make_url(os.environ["TEST_DATABASE_URL"])
    if url.get_backend_name() != "postgresql":
        pytest.fail("TEST_DATABASE_URL must point to PostgreSQL")
    url = url.set(drivername="postgresql+psycopg")
    schema = "test_compute_" + uuid4().hex
    admin = create_engine(url)
    quoted_schema = admin.dialect.identifier_preparer.quote(schema)
    with admin.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {quoted_schema}"))
    scoped_url = url.update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped_url)
    try:
        # Alembic uses the same isolated search path, including its version table.
        monkeypatch.setenv(
            "DATABASE_URL", scoped_url.render_as_string(hide_password=False)
        )
        backend = Path(__file__).resolve().parents[1]
        config = Config(str(backend / "alembic.ini"))
        config.set_main_option("script_location", str(backend / "migrations"))
        command.upgrade(config, "head")
        command.check(config)
        sessions = sessionmaker(engine)
        monkeypatch.setattr(cli, "SessionLocal", sessions)
        monkeypatch.setattr(hourly, "SessionLocal", sessions)
        advisory_calls = []

        @event.listens_for(engine, "before_cursor_execute")
        def record_advisory_lock(
            connection, cursor, statement, parameters, context, executemany
        ):
            if "pg_advisory_xact_lock" in statement:
                advisory_calls.append(statement)

        def pair(self, chain_id, height):
            if height == 3:
                raise ValueError("historical gap")
            return (
                {"result": {"block": {"header": {"time": "2026-01-01T00:00:00Z"}}}},
                {"result": {"height": str(height)}},
            )

        monkeypatch.setattr(cli.ChainClient, "block_pair", pair)
        assert cli.archive_chain("https://fixture.invalid", "test", 1, 2) == 2
        assert cli.archive_chain("https://fixture.invalid", "test", 1, 2) == 0
        with pytest.raises(ValueError, match="historical gap"):
            cli.archive_chain("https://fixture.invalid", "test", 1, 3)
        with sessions() as session:
            assert session.get(Checkpoint, "chain:test:1").height == 2
            assert session.scalar(select(func.count()).select_from(RawBlock)) == 2
        assert advisory_calls, "archive path must exercise PostgreSQL advisory locks"
        advisory_calls.clear()
        hour = datetime(2026, 1, 1, tzinfo=timezone.utc)
        observation = hour.replace(minute=55)
        with sessions.begin() as session:
            session.add(Provider(id="p", first_seen_at=hour, last_seen_at=hour))
            session.flush()
            session.add(
                CapacitySnapshot(
                    provider_id="p",
                    collected_at=observation,
                    observed_at=observation,
                    is_online=True,
                    active=8,
                    available=2,
                    pending=0,
                    total=10,
                    source="fixture",
                    scope="provider_aggregate",
                )
            )
        first = hourly.aggregate_capacity_hour(hour)
        assert first["utilization"] == 0.8
        assert hourly.aggregate_capacity_hour(hour) == first
        assert len(advisory_calls) == 2
        with sessions() as session:
            assert (
                session.scalar(select(func.count()).select_from(MarketMetricHourly))
                == 1
            )
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {quoted_schema} CASCADE"))
        admin.dispose()
