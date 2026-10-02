# Compute Market Research Dashboard

A research workbench for GPU compute-market microstructure, starting with Akash. Explore competition, capacity, concentration, and the orders behind prices. Akash is a transparent market laboratory, not a representative global GPU price index.

## Scaffold status

Implemented:

- Next.js/TypeScript dashboard: `/market`, `/orders`, `/orders/[id]`, `/providers`, `/research`.
- ECharts visualizations, GPU/date/region filters, order drilldowns, and CSV export.
- FastAPI with explicit synthetic demonstration mode and live database queries.
- SQLAlchemy models and an initial Alembic migration for Postgres.
- Restartable raw block/results archival and inventory snapshots with source freshness checks.
- Version-limited marketplace decoding and replay, validated against real GPU auctions with native prices and transaction provenance.
- A recurring inventory worker, capacity-only hourly metrics, and pure price/HHI/dispersion helpers.
- Container definitions, optional local Compose, CI, and an application-only Akash deployment template for an external database.

**Not yet implemented:** full historical-version coverage/backfill, historical FX ingestion, live price/competition/research feature aggregation, regressions, independent backup automation, or a public deployment. Archival and decoding are separate jobs. The decoder supports typed marketplace v1 events and deployment resource messages v1beta3/v1beta4; the included real sample validates v1beta4. Unsupported events and missing antecedents remain explicit partial coverage. Synthetic demo fixtures are never written to research tables.

No Neon connection, hosting account, funded Akash lease, or live collector is configured by default.

## Run the demo without a database

Requires Python 3.11+ and Node.js 22+ with npm. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -c backend/requirements.lock -e './backend[dev]'
DEMO_MODE=true .venv/bin/uvicorn compute_market.api.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd apps/web
npm ci
API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Open <http://localhost:3000/market>. Interactive API documentation is at <http://localhost:8000/docs>. Demo timestamps are fixed in September 2026; use an unfiltered range or select those dates. `DEMO_MODE` is a backend setting. API failures never trigger a synthetic fallback.

## Optional local Postgres

Docker is optional and is not required for the database-free demo above.

```sh
cp .env.example .env
docker compose up --build
```

This creates a local database volume, applies migrations, and starts API and web. The collector is excluded unless the `collection` profile is explicitly enabled. The default local interface remains synthetic; set `DEMO_MODE=false` to view your collected data.

To use any independently provisioned PostgreSQL instance later, set `DATABASE_URL` with the SQLAlchemy `postgresql+psycopg://` scheme, then run:

```sh
cd backend
../.venv/bin/alembic upgrade head
```

Environment variables must be exported or supplied by your process manager. Python commands do not automatically load the root `.env`; Docker Compose reads it. Keep credentials out of git and out of frontend public variables.

## Inspect a real historical sample without hosting

The repository includes 59 public block/result pairs from **two separate intervals**, about 5 MB of evidence. Their checksums and exact coverage are in `backend/tests/fixtures/akash/manifest.json`. They include a successful RTX3090 auction with two bidders and an unsuccessful P40 request. This is a selected validation sample, not a market-wide dataset.

To load this evidence into a small, ignored SQLite preview database, run from the repository root:

```sh
mkdir -p .local
export DATABASE_URL="sqlite:///$PWD/.local/observed.db"
(cd backend && ../.venv/bin/alembic upgrade head)
.venv/bin/python -m compute_market.jobs.sample --directory backend/tests/fixtures/akash
DEMO_MODE=false .venv/bin/uvicorn compute_market.api.main:app --host 127.0.0.1 --port 8000
```

Stop a previous demo API before reusing port 8000. Start the frontend as above, then visit `/orders` or [the validated RTX3090 order](http://localhost:3000/orders/akashnet-2%2Fakash10czfq8xx8nh92ue7svg4t5ffs0lhsd6rxeaqwe%2F1790795508665%2F1%2F1). Replay is idempotent. Native prices retain their exact source strings; no USD conversion or historical capacity is invented. SQLite is only a preview/test option; production remains PostgreSQL. [Reconciliation details](docs/reconciliation.md).

## Data jobs

These commands perform real network collection and require a configured database with migrations applied. Do not run them for the synthetic demo.

```sh
# One inventory observation
.venv/bin/python -m compute_market.jobs.cli inventory

# Recurring observations, default interval 600 seconds
.venv/bin/python -m compute_market.jobs.worker

# Explicit bounded historical archival; choose a node retaining these heights
.venv/bin/python -m compute_market.jobs.cli chain \
  --rpc-url https://YOUR_ARCHIVE_RPC \
  --start-height START_HEIGHT --end-height END_HEIGHT

# Decode the same already archived contiguous range
.venv/bin/python -m compute_market.jobs.cli decode \
  --start-height START_HEIGHT --end-height END_HEIGHT

# Recompute a completed hour's capacity metrics
.venv/bin/python -m compute_market.jobs.cli hourly --hour 2026-09-30T12:00:00+00:00
```

Use one inventory worker. Resume chain archival with the same start height so the checkpoint name remains stable. Raw records have chain/height identity, and checkpoints advance in the same transaction as storage. Inventory remains provider-aggregate until model-specific counts are supported by evidence.

## Validation

```sh
.venv/bin/python -m pytest backend/tests
cd apps/web
npm run typecheck
npm run format:check
npm run build
```

Offline Python tests use SQLite to verify application behavior. CI additionally exercises Postgres where configured; SQLite checks do not prove PostgreSQL-specific behavior. No tests require an Akash node or a hosted account.

## Architecture and research

- [Architecture and parallel ownership](docs/architecture.md)
- [Metric definitions and caveats](docs/methodology.md)
- [API contract, units, and filter semantics](contracts/api.md)
- [Real GPU-auction reconciliation](docs/reconciliation.md)
- [Decoder scope and replay](docs/decoder.md)
- [Source adapters and collection commands](docs/data-sources.md)
- [Public hosting and data survival](docs/deployment.md)
- [Milestones for a public site](docs/launch-plan.md)
- [Research workflow](research/README.md)

The production target is application services on Akash with a separately hosted Postgres database, initially Neon. Deployment templates remain unconfigured until the scaffold is reviewed. Use independent backups before relying on the dataset.

## Contributing

Data/Research owns ingestion, normalization, analytics, and methodology. Product/Infrastructure owns migrations, API contracts, UI, and runtime configuration. Coordinate schema changes before editing shared models. Every aggregate must state its units, population, time convention, and missing-data behavior.

Use conventional commit names (`feat:`, `fix:`, `docs:`, `test:`, `chore:`), descriptive branch names, and focused milestones. Never commit secrets, raw credential-bearing responses, dependency directories, or production database dumps.
