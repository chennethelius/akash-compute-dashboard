# Research API contract

All `/v1` JSON responses contain `meta` and `data`. `meta.mode` is `live` or `demo`; `label`, `as_of`, and `coverage_note` identify provenance and limitations. `as_of` is response time in live mode, **not** proof that observations are fresh. Check observation timestamps and coverage separately. `DEMO_MODE=true` enables deterministic synthetic fixtures; it never writes fixtures to database tables. CSV includes a `data_mode` column. Database errors return HTTP 503, never a demo fallback.

## Filters and units

Collection endpoints accept `gpu_model`, `region`, `start`, and `end` where applicable. Dates must be timezone-aware ISO 8601 timestamps. Intervals are `[start, end)`; `start >= end` returns 422. GPU/region matching is exact. Orders filter on requested GPU/region and order creation time; providers filter on provider region and inventory observation time. These are different geographic concepts. Region and GPU assignment are not inferred from aggregate inventory.

`/v1/orders` supports `limit` (1–1000, default 100) and nonnegative `offset`; newest orders sort first with ID as tie-breaker. IDs are opaque, chain-qualified strings and may contain slashes; URL-encode them for detail links. CSV exports all matching orders, independent of list pagination.

Resource memory/storage fields use bytes; `cpu_units` retains native requested units (not an inferred core count). GPU counts are integer devices. Capacity is reported allocation/availability, not processor load. Utilization is `active / (active + available)` and excludes pending; a missing input or zero denominator yields null. HHI uses a 0–1 scale, effective providers are `1 / HHI`. Current live HHI uses reported total GPU capacity among fresh, online providers with complete counts.

Normalized `price`, `median_price`, `lowest_bid`, `median_bid`, `highest_bid`, `winning_price`, and provider price statistics refer to **USD resource-bundle cost per GPU-hour**, not isolated GPU rental price. Native bid price is separately preserved as a decimal string with denomination; no FX or block-time conversion is implied by native amount. Null means unavailable, not zero. Live price normalization is not populated by the current archive collector.

## Endpoints

| Endpoint | `data` shape / purpose |
| --- | --- |
| `GET /health` | Unwrapped process liveness: `status`, `mode`. Does not test database readiness. |
| `GET /v1/coverage` | Raw block/snapshot counts, normalized order count, decoding status counts, stream checkpoints (`name`, `height`, `updated_at`). Counts/checkpoints do not assert gap-free chain coverage. |
| `GET /v1/market/summary` | `active_gpus`, `available_gpus`, `total_gpus`, `utilization`, `active_providers`, `orders_24h`, `leases_24h`, `median_winning_price`, `median_bidders_per_order`, `provider_hhi`. Capacity comes from latest matching hourly row; prices and auction counts are nullable. |
| `GET /v1/market/timeseries` | Array with `timestamp`, `gpu_model`, metric fields. Capacity rows additionally expose `observation_cutoff`, `provisional`, `freshness_minutes`, excluded-provider counts, `scope`, and `concentration_basis`. Unfiltered requests select aggregate rows, not sums of model/region rows. |
| `GET /v1/orders` | Array: `id`, `created_at`, resource fields, `region`, `bid_count`, bid price summaries, `winner`; currently also includes detail fields. |
| `GET /v1/orders/{id}` | Order plus `bids`, `leases`, `attributes`, `provenance`, and `market_at_order`. Each bid includes `id`, `provider_id`, `provider_name`, `price`, `native_price` (live), `denom`, `created_height`, `created_at`, `state`, `is_winner`, `provenance`. Leases expose provider, native winning price/denomination, creation height/time, nullable observed close time, and source provenance. Missing order returns 404. |
| `GET /v1/providers` | Array: `id`, `name`, `region`, `gpu_model`, inventory counts, `wins`, `bid_count`, `average_bid`, `average_winning_price`, `win_rate`, `market_share`, `first_seen_at`, `last_seen_at`. |
| `GET /v1/providers/{id}` | Single provider using same fields; missing provider returns 404. |
| `GET /v1/research/observations` | Array: `order_id`, `timestamp`, `gpu_model`, `bidder_count`, `winning_price`, `utilization`, `provider_hhi`, `bid_spread`, `available_gpus`. Currently synthetic mode only. |
| `GET /v1/exports/orders.csv` | Matching order/resource/bid-summary columns plus `data_mode`; potentially executable spreadsheet text is escaped. |

Bid count is distinct observed providers bidding no later than the earliest recorded lease selection, using block/phase/transaction/event ordering when source coordinates exist. It does not establish actual eligibility. Detail retains late bids for audit. Newly decoded winner flags match the selected bid identity including bseq; legacy rows lacking bid identity fall back to lease provider identity. Native prices are exact source strings; normalized USD may remain null.

## Intentional live limitations

The chain job archives raw blocks/results and checkpoints. A separate version-limited decode job now creates normalized orders, bids and leases from supported successful events and records explicit partial coverage. See `docs/decoder.md` for supported versions and the validated historical sample. Research observations remain empty, order-time joins remain null, and provider wins/pricing/share statistics remain null. No regression or causal inference is exposed.

Inventory collection stores provider-level totals with unknown `gpu_model`; model and region hourly metrics are not yet computed. Fresh hourly metrics require online status, collection freshness, and source `lastCheckDate` freshness. That source timestamp is a health-check proxy, not guaranteed inventory measurement time. Provider list inventory displays the latest observation in the selected interval; it is not itself a freshness-qualified market aggregate. Provider first/last seen denotes observation, not verified market entry/exit.

Synthetic fixtures cover H100 over 2026-09-29/30; their aggregate timeseries has no regional attribution, so region-filtered timeseries is empty. Demonstration patterns are not empirical results.
