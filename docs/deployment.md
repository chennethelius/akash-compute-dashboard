# Public hosting plan

The intended production architecture is a public Next.js service, private FastAPI service, and one collection worker on an application host such as Akash, with PostgreSQL at Neon. Nothing in this scaffold provisions a cloud account, buys a lease, or connects to a hosted database.

## Services

| Service | Image context | Command | Configuration |
| --- | --- | --- | --- |
| Web | `apps/web` | Image default | `API_BASE_URL`, `HOSTNAME=0.0.0.0` |
| API | `backend` | Image default | `DATABASE_URL`, `DEMO_MODE=false` |
| Worker | `backend` | `python -m compute_market.jobs.worker` | `DATABASE_URL`, `SNAPSHOT_INTERVAL_SECONDS=600` |
| Migration release job | `backend` | `alembic upgrade head` | `DATABASE_URL` |

Expose only the web service publicly. It calls the API on the server and proxies CSV downloads. Database credentials belong only in the API, worker, and migration environment. No database credential uses a `NEXT_PUBLIC_` variable. Use a dedicated application database role for production and TLS when connecting to hosted Postgres. For migrations and collection jobs, start with a direct or session-pooled connection rather than assuming transaction pooling is compatible with all operations.

`deploy/akash.sdl.yaml` is a template for the application services with an external database. It deliberately contains replacement markers and no credentials. It has not been submitted to an Akash provider or validated against a live bid. Publish versioned images, substitute configuration in a private copy, validate it with the current Akash tooling, review resource pricing, and run migrations before starting collection. Storage/pricing parameters are examples, not a cost estimate. The browser URL, custom domain, and HTTPS configuration are finalized with the selected provider.

## Before public launch

1. Select a database region near the application host and record the selected plan's recovery settings.
2. Configure database credentials through the hosting environment, not git or browser code.
3. Run migrations against the new database, then launch API and web.
4. Keep `DEMO_MODE=true` only for an explicitly synthetic preview. Set it to `false` to expose collected data. Empty normalized order tables remain empty until a validated decoder exists.
5. Enable one worker instance. It immediately collects inventory, then repeats every ten minutes. Historical chain backfill remains an explicit bounded job.
6. Configure independent backups, test restoration to a separate database, and measure storage growth before broad backfill.
7. Add uptime checks, job-failure alerts, database-size alerts, and a budget limit/alert. These external services are not provisioned here.

## Data survival

Application-host failure may interrupt the website and collection but does not delete a separately hosted database. A database-host failure still requires that host's recovery process or independent backups. GitHub contains code, not database records. Provider inventory observations lost during collection gaps generally cannot be reconstructed from the chain.

Before ingestion at scale, measure bytes per archived block, bytes per inventory run, table/index sizes, and daily WAL/backup growth. Estimate retained volume from the measured rates. Full raw blocks can dominate storage; a later object-storage archive adapter can reduce the amount retained inside Postgres. It is not implemented in this scaffold.

## Optional local environment

`docker compose up --build` runs a local demonstration stack with Postgres. It does not start the collector. `docker compose --profile collection up --build` explicitly enables live inventory collection into the local database. Local database state lives in the `postgres_data` Docker volume; deleting that volume removes that local data. Docker is optional for running the synthetic API and website.
