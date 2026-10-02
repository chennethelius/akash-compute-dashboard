# Continuous collection operations

Run two independent processes so slow archival or decoding does not delay inventory snapshots:

- `python -m compute_market.jobs.worker`: inventory plus capacity aggregation, every 600 seconds by default.
- `python -m compute_market.jobs.chain_worker`: bounded chain archival followed by marketplace decoding.

Deploy one instance of each. These commands need an already migrated database and a host that keeps processes running. Starting them on a laptop does not make collection independent of that laptop.

## Managed database connection

Create/select the Neon project and database, then obtain a direct connection from its Connect dialog. See [Neon's connection instructions](https://neon.com/docs/connect/connect-from-any-app). Preserve its TLS query parameters. Standard `postgresql://` and `postgres://` URLs are mapped internally to the installed psycopg driver; `postgresql+psycopg://` also works.

Store `DATABASE_URL` in the host's secrets/environment settings. For local preparation, put `export DATABASE_URL='...'` in the gitignored `.env.local`, then source that file in the shell. Python jobs do not load dotenv files automatically. Do not put the connection string in command history, source control, or browser configuration.

From `backend/`, with the environment set:

```sh
alembic upgrade head
alembic check
```

Start the API and check `/ready`. `/health` only confirms the process responds; `/ready` queries core database tables and returns 503 if they are unavailable. Readiness does not verify every migration, data freshness, backups, or decoder completeness. Use `alembic check` and coverage checks as well.

## Chain worker settings

| Variable | Meaning |
| --- | --- |
| `AKASH_RPC_URL` | Required node retaining the selected block history |
| `AKASH_CHAIN_ID` | Expected chain, defaults to `akashnet-2` |
| `CHAIN_START_HEIGHT` | Required positive first height; keep stable across restarts |
| `CHAIN_BATCH_SIZE` | 1–100 blocks per cycle, default 20 |
| `CHAIN_POLL_SECONDS` | Wait after a successful cycle, default 30, minimum 5 |
| `CHAIN_MAX_RETRY_SECONDS` | Exponential retry cap, default 300 |

Each batch makes sequential RPC requests, limited to the configured block count, then waits. This is a throughput bound, not a strict per-second API quota. Set batch size and poll interval for the selected provider's limits. Requests have 30-second timeouts; a shutdown signal finishes the bounded batch before exiting. Configure sufficient shutdown grace time for a slow batch.

The archival checkpoint is `chain:<chain>:<start>`. The separate projection checkpoint is `projection:<chain>:<start>:<decoder-version>`. A decode transaction saves its report and checkpoint together. Failed blocks are retried; successful earlier work is retained. Missing raw blocks prevent projection progress. Retried work does not require redownloading already archived blocks.

The projection checkpoint means **attempted through this height**, not fully decoded through this height. Unsupported messages and missing antecedents produce partial reports in `block_projections`. These do not halt subsequent blocks; `/v1/coverage` reports partial coverage separately. Decoder-version changes create a fresh projection checkpoint and replay the selected interval; normalized-event reprocessing semantics still need review for changes in decoder meaning.

Do not change the start height to hide a stalled block. A deliberate new interval needs a separately documented coverage boundary. Standalone `jobs.cli decode` remains available for explicit bounded replay and does not advance the worker checkpoint.

`job_runs` records each cycle's completion or failure. Chain-worker errors store exception type rather than URLs or credentials. A hard process kill can leave a running row unfinished; it does not advance the failed transaction's checkpoint. External monitoring of recent successful cycles is still required.

## Local validation and hosting

The optional Compose `chain-collection` profile starts the chain worker only when explicitly enabled. Configure RPC/start height first. It uses the local Compose database, not Neon. To collect both streams locally, enable both `collection` and `chain-collection` profiles. The default demo remains opt-in for collection.

On the production host, run the same backend image as two separate worker services using the commands above, with `DATABASE_URL` supplied privately. The existing Akash template contains only the inventory worker; add a separately sized chain worker when its starting height and RPC have been chosen. Do not run a broad backfill automatically during deployment.

Before unattended production use: verify restart behavior on Postgres, test a separately stored backup restore, monitor source freshness and checkpoint lag, and measure storage growth on a modest contiguous window. Neither external monitoring nor a hosted backup destination is provisioned by this repository.

## Validation evidence

Automated tests cover bounded batches, resume after a decode exception, partial coverage, checkpoint gap rejection, capped retry delays, connection-string preservation, and database readiness failure. The PostgreSQL CI test also runs worker batches over the real archived auction fixtures.

A live smoke run on 2026-10-02 fetched Akash heights 28860258–28860263 from `https://rpc.akt.dev/rpc` into an isolated temporary SQLite database: four complete block reports, two partial reports, and 15 decoded actions. This verifies a small end-to-end batch, not historical node retention, continuous uptime, or production deployment.
