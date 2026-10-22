# ADR 039: A Single Uvicorn Worker for the API

**Status:** Accepted
**Relates to:** [ADR 038](./038_domain_metrics_derived_not_counted.md), [ADR 019](./019_api_and_scheduler_container_separation.md), [ADR 026](./026_lazy_loading_ephemeral_ml_models.md)

## Context

`prometheus_client` keeps its registry in the memory of the process that owns it. With `--workers 2`, Uvicorn spreads requests, the scrape included, across two independent processes, each with its own counters. Prometheus scrapes one or the other at random every 15 s, so each series jumps between two different histories. The graphs still draw; they just describe half the traffic. The data is not missing, it is wrong.

## Decision

Run the API with one worker (`--workers 1` in `docker-compose.prod.yml`).

The reason is correctness, but the decision stands even without Prometheus. The API is asynchronous: I/O concurrency comes from the event loop, not from processes. Its only CPU-heavy work, computing the query embedding, already runs in a thread via `asyncio.to_thread`. On 2 vCPU that also run FinBERT, two workers competed for CPU while duplicating the same libraries in RAM.

## Alternatives rejected

- **`prometheus_client` multiprocess mode**, the textbook answer. It needs a directory shared by the workers (ideally tmpfs), a `mark_process_dead(pid)` call whenever a worker dies or stale metrics stay on disk, and gauges lose their meaning: they only aggregate as `livesum`, `max` or `min`, not "current value". Three moving parts to keep a second worker that was not earning its place.
- **Living with inconsistent metrics.** Rejected outright: a metric that is wrong half the time is worse than none.

## Consequences

- **Memory:** two workers used 765 MB of anonymous memory (395 + 394 MB), because each imports torch and sentence-transformers at start-up, ~390 MB before any model weights. One worker: 296 MB at rest, peak 422 MB over five days.
- **The compose limit stays at 1.25G on purpose.** A limit is a ceiling, not a reservation: lowering it frees nothing for other containers, it only moves the point where the OOM killer steps in.
- **Single point of failure, accepted.** If the process dies the API is down until Docker restarts it (`restart: unless-stopped`). With two workers the likely failure was OOM anyway: 12,833 limit hits and one `oom_kill` under the earlier 512M limit.
