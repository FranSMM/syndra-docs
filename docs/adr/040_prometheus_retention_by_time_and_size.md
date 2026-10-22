# ADR 040: Prometheus Retention by Time and by Size, Sized on Measured Cardinality

**Status:** Accepted
**Relates to:** [ADR 038](./038_domain_metrics_derived_not_counted.md), [ADR 018](./018_vps_provider_hetzner_selection.md), [ADR 022](./022_immutable_gitops_infrastructure.md)

## Context

Prometheus supports two retention limits, and they protect different things. **Time** keeps the history: six months of metrics are needed to evaluate the system over its life. **Size** protects the machine: a Prometheus with no size cap filling the disk is a known failure, and it is exactly the one this cap exists to prevent.

The first plan set the size cap to 2 GB, from a published rule of thumb of 1.5 to 2 bytes per sample that assumed ~100 series. The real count was 835 series from the API alone and 3,368 once cAdvisor and node exporter were added. At that rate 2 GB would have been reached around day 150 of 180: the size cap would have taken over silently and started deleting the oldest data, which is the history the time limit was meant to keep.

## Decision

`retention.time=180d` and `retention.size=10GB`.

The number matters less than the rule: **time must be the limit that governs, and size only a safety net.** When the order inverts, Prometheus deletes the oldest blocks without warning.

Sized on measurement, not estimates. On 16/09/2026, after a week of collection, `delta(prometheus_tsdb_storage_blocks_bytes)` gave 24.7 MB/day over both a 24 h and a 5 d window; two independent windows agreeing to the decimal is what makes the figure trustworthy. That is 1.53 bytes per sample and 4.45 GB at 180 days, 44 % of the cap. An earlier reading of 28.1 MB/day used `du -sh` on the whole directory, which includes ~25 MB of WAL that stays constant; `storage_blocks_bytes` counts only closed blocks, which is what grows.

## Alternatives rejected

- **Time only.** Nothing stops a cardinality spike from filling the disk.
- **Size only.** History length becomes whatever fits, and the oldest data goes first.
- **Tighten the cap to 5 GB now that it is measured.** The cap only has to keep Prometheus from filling a 75 GB disk with 44 GB free. Time already governs with room to spare; tightening a safety net that is not in the way is change for its own sake.

## Consequences

- Time governs again, with a 56 % margin on size.
- `check-observability.sh` projects with 1.75 bytes per sample, not the measured 1.53, on purpose: the projection protects a disk, and erring high warns early.
- Adding scrape targets changes cardinality. Re-measure before trusting the projection.
