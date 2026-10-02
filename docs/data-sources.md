# Data sources and collection

Source documentation reviewed 2026-10-01:

- [Akash Providers API](https://akash.network/docs/api-documentation/rest-api/providers-api/): `GET https://console-api.akash.network/v1/providers`, provider ownership and aggregate `stats.gpu` fields.
- [GPU availability guide](https://akash.network/docs/api-documentation/rest-api/gpu-availability-guide/): GPU descriptions are embedded in provider responses.
- [Provider monitoring](https://akash.network/docs/providers/operations/monitoring/): operational inventory context. Active indicates resources consumed by deployments; API version semantics for reservations and pending capacity require further reconciliation.
- [CometBFT RPC source specification](https://github.com/cometbft/cometbft/blob/main/rpc/openapi/openapi.yaml): block, block_results, and status endpoints. Historical access depends on the node's retention and RPC version.

## Jobs

Run after migrations, with DATABASE_URL set and the Python package installed:

```sh
python -m compute_market.jobs.cli inventory
python -m compute_market.jobs.cli chain --rpc-url "$AKASH_RPC_URL" --start-height 10000000 --end-height 10000010
python -m compute_market.jobs.cli decode --start-height 10000000 --end-height 10000010
python -m compute_market.jobs.cli hourly --hour 2026-10-01T12:00:00+00:00
```

The example height is illustrative, not a guaranteed retained range. Specify an archive-capable RPC endpoint and the intended chain ID. Reuse the same start height to resume that checkpoint stream. Without end height the chain job archives up to the tip observed at invocation and exits; run periodically for incremental collection. Indexing retries happen by rerunning the job; failures do not advance its checkpoint.

Schedule inventory every ten minutes using cron or a worker. Scheduling is configuration to activate on a deployed host, not an already-running service. Run the hourly command for each completed UTC hour; reruns overwrite that version's derived row. Do not schedule a large backfill every ten minutes.

Inventory projections link to their raw response. Failed HTTP requests create no capacity observation; they must be monitored as job failures. A successful response does not establish source freshness. Projections retain the reported health-check timestamp and online status; hourly aggregation excludes missing, stale, future-dated or offline observations. The collector does not mark absent providers inactive.

## Still required before research use

Broader historical message/version coverage, authz/reopened-order resource reconstruction, FX and measured block-interval provenance, actual eligible-provider attribution, model-specific inventory where available, and historical completeness audits. The version-limited decoder now validates successful-only execution, native bid prices, requested resources, and selected lease identities against a small real sample. This is not a completed historical dataset. No Allium dependency or external price benchmark is included.

## Hosted worker

```sh
python -m compute_market.jobs.worker
```

Set `DATABASE_URL`, optionally `AKASH_CONSOLE_URL`, and `SNAPSHOT_INTERVAL_SECONDS` (default 600; minimum 30). Run migrations before starting. The worker snapshots immediately, refreshes previous and current hourly capacity rows, then waits the configured interval. Current-hour values are provisional and use the collection-time cutoff; completed hours use their hour-end cutoff. Failed cycles are logged and retried after the interval; no tight retry loop or automatic chain backfill occurs. SIGTERM/SIGINT stop scheduling and allow the current cycle to finish. Run a single worker instance to avoid duplicate simultaneous snapshots. Completed cycle status is stored in `job_runs` when the database is available.
