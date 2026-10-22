# ADR 041: ETL Stage Metrics Derived from Prefect's Database

**Status:** Accepted
**Relates to:** [ADR 038](./038_domain_metrics_derived_not_counted.md), [ADR 005](./005_prefect_for_data_orchestration.md), [ADR 019](./019_api_and_scheduler_container_separation.md)

## Context

Nothing measured the ETL's latency per stage, and evaluating the pipeline needs exactly that.

Instrumenting the stages in process does not work. The scheduler calls `etl_flow.serve()`, which stays up and launches the flow every 60 minutes, but Prefect runs each flow run in a **subprocess** (`Runner._run_process`, Prefect 3.8.5: "Runs the given flow run in a subprocess."). A counter in the parent, the one that would expose `start_http_server()`, would see none of the four stages. It is the per-process registry problem of ADR 039 in another place.

Then the finding that changed the plan: Prefect does not keep its state in SQLite inside its container. It uses `prefect_db` in our own Postgres. On 16/09/2026 it held 14,904 task runs since 07/04/2026: five months of per-stage durations, with timestamps and states, already recorded without any instrumentation.

## Decision

Derive the ETL gauges from `prefect_db`, applying the principle of ADR 038 for a new and stronger reason: here it was the only option that could work.

- **A second, read-only engine** in `app/db/session.py` with `pool_size=1` and `max_overflow=1`: it answers two aggregate queries a minute, not requests. Nothing is ever written to that schema; Prefect's server owns and migrates it.
- **Its own 60 s cache and last-success gauge**, separate from ADR 038's, so a Prefect outage does not take the domain gauges with it.
- **Strip the hash suffix.** Prefect names task runs `<stage>-<hash>` (`Load: PostgreSQL async-f49`). Used as a label, every run would become a new series. The query normalises it with `regexp_replace(name, '-[0-9a-f]+$', '')`.

## Alternatives rejected

- **Pushgateway.** It exists for jobs that finish before Prometheus can scrape them, and `syndra_scheduler` never finishes. That alone would point back to in-process instrumentation, which the subprocess rules out. The right conclusion is not Pushgateway but deriving.
- **Instrumenting the stages in process.** Blind, as above.
- **A dedicated exporter.** Another container for two queries a minute (same argument as ADR 038).

## Consequences

- **Works backwards:** the whole history since April became available at once (Vector Indexing 3,726 runs, mean 8.59 s, p95 9.05 s, 0 failures).
- **Cost:** up to two extra connections to Postgres.
- **Depends on a schema we do not own.** A Prefect upgrade can change it; the query breaks loudly and the last-success gauge shows it.
- **Verified** on 10/09/2026 against `psql`: published gauges 9.06 / 8.14 / 3.05 / 2.18 s against 9.053 / 8.107 / 3.047 / 2.182 s.
- **Open risk:** `prefect_db` grows without pruning (145 MB on 09/09/2026, no retention configured). Same family as a full disk.
