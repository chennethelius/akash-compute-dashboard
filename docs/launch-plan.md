# From validated sample to public research site

The current milestone is a working interface and a reproducible historical sample: 59 blocks in two intervals, including a GPU auction with two bids. It is not a continuously indexed market or a complete research dataset. No production database or application hosting is connected.

## 1. Keep new evidence continuously

Connect the agreed managed PostgreSQL database, apply migrations, and deploy a single inventory worker. Configure database recovery, an independent backup destination, a tested restore procedure, and alerts for failed or stale collection. Start inventory collection early: historical capacity before collection cannot generally be recovered from chain replay.

Add a bounded incremental chain loop that archives then decodes, with retry/backoff, rate limits, gap detection, and distinct archival and projection checkpoints. Preserve a stalled block as a visible failure rather than advancing coverage past it. Choose and test a historical RPC source before scheduling backfills.

Exit condition: jobs recover from a deliberate interruption without duplication, source timestamps remain visible, and a backup has been restored to a separate test database. A hosted database without hosted workers does not collect data.

## 2. Expand validated market coverage

Backfill a modest contiguous window first, then expand after measuring storage growth and decoding exclusions. Add fixtures for historical upgrades, authz-wrapped requests, reopened orders, resource updates, and provider lifecycle events. Reconcile a sample of bids/leases against source evidence for every supported version.

Build the actual price/competition aggregates: distinct pre-selection bidders, bid spread, selected bid, denominated bundle cost, and separate concentration definitions. Hourly/USD conversions require measured block timing and explicit denomination/FX provenance. Cohorts must distinguish GPU variants, quantities, and accompanying resources. Match only sufficiently fresh capacity observations preceding auctions; leave unavailable matches null.

Exit condition: charts reconcile to downloadable underlying orders, and every metric reports sample size, units, time convention, exclusions, and coverage. Zero-bid orders remain in the population. Unknown historical availability is not backfilled with current inventory.

## 3. Make reads suitable for public traffic

The scaffold intentionally favors inspectability over throughput. Before public launch:

- Replace per-order bid/lease lookups with batched queries; paginate providers and the order explorer.
- Bound timeseries/research query windows and export sizes; stream CSV instead of buffering a complete export in memory.
- Add short-lived caching to aggregated views with visible source freshness. Cache identity must include filters, dataset mode, and metric version.
- Add indexes based on measured query plans, plus database connection budgets and statement timeouts.
- Add a database-readiness check separate from process liveness, and alerts for ingestion lag, projection failures, API errors, storage growth, and backup failures.
- Keep database credentials server-side, use limited database roles, and add request limits to public read/export endpoints.

Measure performance against a representative dataset and expected concurrency before choosing larger compute. Scale API/web processes separately from the single ingestion writer. PostgreSQL remains the initial store; additional database engines are not a prerequisite.

## 4. Publish a clearly scoped alpha

Deploy versioned web/API images using the existing application-only hosting template; the production database stays separate from the application provider. Configure a domain and HTTPS, verify mobile/desktop pages, run a restore and rollback drill, and publish a visible coverage/methodology page. The first alpha can be read-only with no user accounts.

Show the actual observation period and latest collection time rather than implying that an API response timestamp means fresh market data. Keep incomplete charts empty and explain why. An Akash application-provider outage may interrupt collection and serving, but should not remove the separately hosted dataset.

Exit condition: a public URL works without local processes, jobs run while the developer laptop is off, filtered chart-to-order drilldowns and CSV exports pass checks, and data gaps are understandable to visitors.

## Storage and later expansion

Measure bytes per block/snapshot and daily table/index/recovery-history growth before a large backfill. Move bulk raw evidence to checksummed object storage when justified, keeping normalized records, archive references, and research features in PostgreSQL. Keep source response files separate from independently restorable database backups.

After the public Akash dataset is reliable, evaluate licensed Ornn/Silicon Data integration with explicit benchmark mappings and redistribution terms. Regressions, forecasts, forward curves, and asset valuation follow sufficiently broad data and validated definitions; they are not launch prerequisites.
