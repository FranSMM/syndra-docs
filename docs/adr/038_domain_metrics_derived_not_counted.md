# ADR 038: Domain Metrics Derived from the Database, Not Counted in Process

**Status:** Accepted
**Relates to:** [ADR 019](./019_api_and_scheduler_container_separation.md), [ADR 024](./024_medallion_architecture_bronze_silver_separation.md), [INC-021](../troubleshooting/021_ticker_false_positives_from_short_symbols.md)

## Context

HTTP metrics come free with the client library and involve no decision. The metrics that describe Syndra itself do: corpus size, freshness per source, the enrichment queue. The obvious implementation is a counter the pipeline increments. Here it is wrong:

- **The work happens in another container.** The scheduler writes to Postgres every hour and shares no memory with the API (ADR 019). A counter in the API would never see it.
- **Counters reset** on every restart, deploy or OOM kill. The corpus has been accumulating for five months.
- **Two copies of the truth diverge.** INC-021 is the precedent: ticker attributions drifted between Qdrant and Postgres unnoticed until compared by hand.

Prometheus' own exporter guidelines say the same in general terms: when a system already holds the state, read it rather than keep a parallel count.

## Decision

Every domain gauge is the result of a SQL query run at scrape time (`app/core/metrics.py`).

- **Two aggregate queries**, one over `articles` and one over `raw_articles`.
- **60 s cache** with a double check inside an async lock, so concurrent scrapes do not run the same SQL twice. Prometheus scrapes every 15 s; without the cache that is four aggregates a minute against the database that serves the API.
- **No `_total` suffix.** These are true gauges: the corpus shrinks if rows are deleted, and `pending` returns to zero whenever the pipeline catches up. `promtool` rejects `_total` on non-counters. Fixed before the first sample was collected, since renaming starts a new series and orphans the history.
- **Labels by source only.** 3 sources against 10,657 tickers: a ticker label would mean 10,657 series per metric on a 3.8 GB machine.
- **A failed refresh is not fatal.** `/metrics` still returns 200 with the HTTP latencies. Stale values would then look current, so `syndra_domain_metrics_last_success_timestamp_seconds` records the last good refresh. Without it, a gauge that was never read is indistinguishable from a real zero.

## Alternatives rejected

- **In-process counters.** Blind to the scheduler's work and reset on restart, as above.
- **A dedicated exporter container.** Another service to deploy and limit on a 3.8 GB box, to run two queries a minute that the API can run itself.
- **Materialised views refreshed by the pipeline.** A second copy of the truth with its own staleness, the INC-021 pattern again.

## Consequences

- **Cost:** at most two aggregate queries per minute.
- **Survives restarts:** the gauges are correct from the first scrape, with no warm-up.
- **Verified** on 10/09/2026 against `psql` by hand: `syndra_articles` per source 66,712 / 217 / 33 and `syndra_articles_with_tickers` 32,641, all exact. Ages per source differed by exactly the 79 s between the two readings. With both databases down, `/metrics` returned 200 with latencies intact.
