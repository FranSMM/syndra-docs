# 06 - Production metrics

**Questions:**

1. How much memory, CPU and disk does each container and the host use against their limits, and were there OOM kills or restarts?
2. How long do the requests of experiment 05 take inside the API, and so how much of the client latency is network?
3. How does the scheduler's memory during the ETL compare with FinBERT alone in experiment 04?
4. How big is the Prometheus TSDB, how fast does it grow, and does the 180-day retention fit under the 10 GiB size cap?

**What is read:** the history that Prometheus, cAdvisor and node_exporter already collect in production, plus the ETL run times in `prefect_db`. Nothing is measured anew and nothing is written on the VPS: `export.py` travels to the server through stdin and only sends GET requests to the Prometheus API on 127.0.0.1, and the `prefect_db` session is forced read-only.

**Run** (from WSL):

    ./measure.sh
    python3 analyze.py results/production_YYYYMMDD_HHMMSS > results/production_YYYYMMDD_HHMMSS_summary.csv

By default the latency windows come from the newest run of 05 and the comparison figures from the newest run of 04; `LATENCY_ENV=...` and `INFERENCE_SUMMARY=...` choose others. The run takes about 15 seconds.

**Raw data**, one CSV per dataset, all sharing the prefix `results/production_<stamp>`:

| File | Content | Step |
|---|---|---|
| `_containers.csv` | Per container: peak working set and RSS, memory limit, start time, OOM counter | 15 min, peaks kept with `max_over_time` |
| `_host.csv` | Raw CPU counters and lowest available memory | 1 min |
| `_storage.csv` | Root filesystem, TSDB blocks and WAL, head series, host boot time | 1 h |
| `_scheduler.csv` | Scheduler working set and RSS | 15 s, last 7 days |
| `_etl_runs.csv` | Start and end of every ETL run, from `prefect_db` | per run |
| `_latency.csv` | Request and histogram counters at both ends of each 05 window | per window |
| `_series.csv` | Active series per scrape job | now |

**Which memory figure:** two are reported. The working set is what the kernel weighs before an OOM kill, and it includes the page cache in active use, such as model files just read. RSS is process memory only, the same quantity as the `VmHWM` that experiment 04 reports, so the comparison with 04 uses RSS. Both are in MiB, like 04.

**Recreated containers:** every deploy recreates containers, and cAdvisor gives each new container a new series. Series are merged by container name with `max()`; reading only one series would miss part of the history.

**Statistics:** samples of a time series are not independent repetitions, since each one depends on the one before, so bootstrap intervals would claim a precision the data does not have. The summary gives nearest-rank percentiles over the samples and always states the step they were taken at. The server latency comes from a histogram, which only tells which bucket a request fell in. Its percentiles are therefore given as the bucket that holds them, such as `(25, 50]` ms, with no more precision than that. The network share is the client percentile from 05 minus that bucket. That is a difference of percentiles, not a percentile of differences, so it is an approximation of where the network share lies.

**Limits of the data:**

- **Short peaks are under-sampled.** cAdvisor reads memory every 15 s (`housekeeping_interval`), and the ETL keeps its models loaded for about that long, so most runs are sampled before or after the peak. The maximum over many runs is the useful figure, and it is a lower bound of the true peak.
- **The ETL minute is not fixed.** The ETL is an hourly interval anchored at the last deploy, so its minute moves with every deploy. The analysis takes each run's real start and end from `prefect_db` rather than assuming a minute.
- **Deploys and crashes look alike.** A container start on its own may be a one-service deploy or a crash, so the summary lists every start group with its containers. Docker's own restart counter and OOM flag, recorded in the environment file, only cover the containers running now.
- **Start dates differ by job.** The API and Prometheus series start on 7 September 2026; cAdvisor and node_exporter start on 10 September 2026. The environment file records the first sample of each job.
- **One endpoint per window.** The high-resolution latency histogram (`http_request_duration_highr_seconds`, buckets of 10, 25, 50, 75 and 100 ms and up) has no endpoint label. It can be read per scenario only because each 05 window ran a single scenario, and the summary counts the requests from any other handler in the same windows. The per-endpoint histogram only has buckets of 0.1, 0.5 and 1 s, too coarse for these latencies.

**Not measured:**

- The kernel log of OOM kills, which needs sudo.
- Container restarts closer together than the 15-minute step.
- Anything before Prometheus was deployed.
