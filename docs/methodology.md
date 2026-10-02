# Research methodology (scaffold v1)

Akash is a transparent microstructure laboratory. Results do not estimate the global GPU market. Hypotheses are unproven: competition may lower prices, scarcity may raise prices nonlinearly, concentration may increase prices, and new capacity may reduce pricing pressure.

## Evidence and coverage

The chain job archives block and execution-result pairs atomically with a restart checkpoint. Its range starts at an explicitly selected height; a checkpoint is not evidence of genesis coverage. Raw block primary keys prevent duplicate history. Failed fetches or validation leave the height unadvanced. A PostgreSQL advisory lock serializes writes per chain. A separate, version-limited decoder projects supported successful events into orders, bids and leases and records per-block issues. The archive job alone does not populate them. Raw tx bytes, events and results remain available for replay. Never label archived blocks as decoded market coverage. See [decoder scope](decoder.md) and [real sample reconciliation](reconciliation.md).

Inventory snapshots preserve each successful provider response and collection timestamp. Provider counts are observations of reporting providers, not the entire network. Missing inventory is unknown, not zero; disappearance is not provider exit. Collection time is not the source observation time. Capacity projections retain `lastCheckDate` as `observed_at` and `isOnline` as `is_online`; the source date is a health-check freshness proxy, not proof of a GPU inventory measurement time. Missing/invalid source dates remain unknown. Failed normalization preserves the raw snapshot but rolls back its entire projection.

## Definitions

- Allocation utilization proxy = active / (active + available). Pending counts are stored separately and excluded from this denominator. This measures reported allocation, not device processing load. Zero denominator returns null.
- Capacity HHI = sum of squared provider shares of reported total GPUs, on a 0–1 scale. Effective providers = 1 / HHI. Empty markets return null. This is distinct from lease-count, spend, or GPU-hour concentration.
- Bid spread = max minus min comparable bid; normalized spread divides by the median. No bids gives null. Bids must share an order, denomination and pre-selection cutoff. Repeated bids by a provider must not increase distinct bidder count.
- Winning bundle cost per GPU-hour = native amount per block / denomination scale × 3600 / observed block seconds / requested GPU count. CPU, memory and storage remain in the bundle. USD requires a dated FX observation. No implicit block interval or FX rate is used.
- Provider first/last seen indicate observations only. Registration, first bid, first capacity and first win are distinct milestones.

Console GPU counts are provider aggregates. `gpuModels` describes hardware and does not allocate those counts across models. Current projections therefore use null GPU model and `provider_aggregate` scope, even for apparent single-model providers. Model-filtered capacity remains unavailable until evidence supports attribution.

## Hourly job

Capacity-v1 selects each provider's latest observation in the final 20 minutes before the hour ends. For the current hour, the cutoff is the job run time and the row is explicitly marked provisional. It first selects the latest collection per provider, then requires online status and a source health-check timestamp within the freshness window and no later than collection. This prevents fallback to a superseded online observation after an offline report. It includes only provider aggregates with active, available and total counts, records freshness/offline and incomplete-count exclusions separately, and weights HHI by reported total GPUs. This is a sample of reporting capacity; it is neither an hourly average nor an assertion of full network coverage. The job is rerunnable with a deterministic key. Marketplace price/competition metrics remain absent until decoding and provenance checks pass.

## Research design

Compare hardware/configuration cohorts, preserve quantities, region requirements, lease duration and provider identity. Prices versus bidder count or capacity are descriptive associations: order attractiveness and restrictive requirements affect both competition and prices. Use observations preceding selection with an explicit freshness bound. Do not join a lease to capacity measured after its allocation. Include unsuccessful and zero-bid orders when studying selection.

Future analysis should report sample sizes, missingness, cohort composition and sensitivity to freshness/cohort definitions. Begin with descriptive plots, then configuration/time controls and provider effects as supported by sample size. Event studies need pre-trend checks and a defensible comparison group. No predictive or causal conclusions are implemented in this scaffold.

Provider display name and IP region are stored separately from the observed attribute list. `attributes.location` preserves IP-derived and declared location fields, and `region_source` identifies `console.ipRegion`; these are provider locations, not requested order regions. Raw snapshots retain their history.
