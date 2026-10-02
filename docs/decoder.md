# Marketplace decoder scope

`python -m compute_market.jobs.cli decode --start-height H1 --end-height H2` processes an already archived contiguous interval. It performs no network calls. Run it after `chain`, or load the checked-in evidence with `python -m compute_market.jobs.sample --directory backend/tests/fixtures/akash`.

The parser supports typed `akash.market.v1` order/bid/lease create and close events, deployment create/close, and group close. Resource extraction reads original transaction protobuf bytes for `/akash.deployment.v1beta3.MsgCreateDeployment` and `v1beta4`. The checked-in mainnet fixtures exercise v1beta4. Schemas are pinned to the official chain-sdk source commit recorded in the decoder; other versions are not assumed compatible.

## Guarantees within supported evidence

- Transactions with nonzero execution codes cannot create projections.
- Transaction hashes are computed from the original decoded base64 transaction bytes.
- Requests sum resource units multiplied by replica count. Raw attributes and group requirements remain in order evidence. Ambiguous GPU model requirements stay null.
- Order identity includes chain, owner, dseq, gseq and oseq. Bid/lease identities additionally include provider and bseq.
- A lease must reconcile to an observed bid, including exact native amount and denomination. The winner comes from the lease event, never a minimum-price guess.
- Native price source strings are retained alongside database Decimal values. SQLite previews use those strings to avoid floating-point round-trip changes; PostgreSQL stores prices as NUMERIC.
- Observed lifecycle events remain in provenance. An absent close means no close observed in the indexed evidence, not proof the lease is currently active.
- Replays do not duplicate rows or clear observed closure state. Conflicting source evidence fails rather than overwriting history. Source timestamps retain their original precision in provenance; SQL timestamps have microsecond precision.

## Coverage and replay

`block_projections` records decoder version, status, event count, and issues separately from raw archival checkpoints. Missing order/bid antecedents are explicit issues; they do not generate invented resources or winning bids. Unrecognized versions/events and malformed resources remain partial. Unknown resource projections cannot justify like-for-like price comparisons.

Replay in ascending height order. If earlier history is added later, rerun the affected later interval to resolve previously missing antecedents. Historical upgrades, authz-wrapped deployments, reopened orders whose requirements originated in a previous transaction, provider registration events, and full resource-update history need further work. A decoder upgrade that changes existing event content requires an explicit rebuild/migration strategy; silently overwriting audited evidence is not supported.

The sample consists of two intervals, not a continuous range between its minimum and maximum heights. It produces 9 orders, 17 bids, 4 leases, and 98 evidence events on the initial decoder. Nine of its 59 blocks are partial due to missing prior history or unsupported events. These counts are validation results, not market statistics.

Inventory at auction time and historical FX are absent from this sample. USD prices, pre-auction capacity and research regressions remain unavailable. No predictive or causal conclusion follows from these fixtures.
