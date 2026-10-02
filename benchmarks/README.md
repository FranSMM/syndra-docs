# Benchmarks

Reproducible experiments backing the figures of Chapter 4 of the dissertation. Each folder is a self-contained experiment following the same template: `README.md` (question, environment, how to run), `measure.sh` (takes the measurements and stores the raw data), `analyze.py` (statistics from the CSV) and `results/` (raw CSVs and environment metadata).

## Index

| # | Experiment | Question | Runs against | Status |
|---|---|---|---|---|
| 01 | [Subprocess startup](./01_subprocess_startup/) | How much of the per-source time is startup and how much is actual work? | production, read-only | Measured |
| 02 | [ETL latency](./02_etl_latency/) | How is latency split across the stages, how did it evolve, and how much does each feed add? | production history, read-only | Ready |
| 03 | [Per-ticker query indexes](./03_jsonb_gin/) | Which index does the per-ticker query need, from what size, and is the Bronze GIN of ADR 012 still used? | local copy of production data | Ready |
| 04 | [Inference resources](./04_inference_resources/) | How do time and memory of FinBERT change from one text at a time to batches? | local, deployed image | Ready |
| 05 | [API latency](./05_api_latency/) | How long does a request take under the load of one client, with the cache warm and cold? | production, 0.4 requests/s | Ready, needs a test key |
| 06 | [Production metrics](./06_production_metrics/) | How much memory, CPU and disk does production use against its limits, how much of the 05 latency is network, and how fast does the TSDB grow? | production history, read-only | Measured |

## Rules

1. **Measuring and analysing are separate steps.** Raw data is always kept, so the analysis can be repeated without measuring again.
2. **Every run records its own environment:** date, repository commit, container image, cores, memory and library versions.
3. **A CSV is never edited by hand.** If a data point is wrong, measure again.
4. **Fixed seed** in anything involving randomness, such as bootstrap resampling.
5. **Fixed repetition count, 30.** The first one is reported separately because of the cache effect: the first import pays for the disk read that later ones find in the page cache. Where an experiment cannot follow this rule (02 uses every recorded run; 05 measures hundreds of requests per run; 06 reads time series, which are not repetitions), its README says why.
6. **Whatever is quoted in the dissertation lives in the repository**, and the dissertation cites the exact commit. If the environment file says `dirty_tree: yes`, some code differed from that commit, so the commit does not identify the measured code and the run cannot be quoted. Files under `results/` and `docs/` do not count; any other change or new file does.

No machine address or credential is written into these files: the SSH target comes from `VPS_USER` and `VPS_IP` in the root `.env`, which is not in git, and API keys are passed through the environment or a git-ignored file. Copies of production data (03 and 04) hold scraped article text, so they live in `~/.cache/syndra-bench/` and never in the repository. Every query against production runs in a session forced read-only.

## Shared code

`lib/` holds what the experiments share, so each `measure.sh` and `analyze.py` only says what is particular to its experiment:

- `common.sh`: reading `.env`, SSH and read-only `psql` against the VPS, the environment header, and a checksum-verified vegeta.
- `stats.py`: nearest-rank percentiles and bootstrap intervals, standard library only.
- `api_targets.py` and `vegeta_csv.py`: the request lists of the API latency experiment and the conversion of vegeta's output into the benchmark CSV.

**Not measured:** the API's capacity, the request rate at which it degrades. Measuring it means pushing the API until it fails, which on the production VPS would break the service and share the two cores with the ETL; it needs a clone of the VPS and is left as future work.

## How this maps to the dissertation

**Experimental setup**, once, at the start of Chapter 4: a 2-core server with 3.8 GB of memory, the ETL image tag, the Python and library versions, the statistical criteria, and a link to this directory at the exact commit. The actual values are copied from the environment file of the run being quoted, not from here.

Statistical criteria, written once and valid for every table: the **median** is reported instead of the mean because network retries and CPU contention produce outliers that shift the mean without being representative; dispersion is given as the interquartile range; the 95 % confidence interval of the median is estimated by **bootstrap** with 10,000 resamples and a fixed seed, following Efron and Tibshirani (1993), *An Introduction to the Bootstrap*, Chapman & Hall.

**Before each table**, a short procedure paragraph: what is measured, how, and how many repetitions. **In each table footer**, n, time window and data source.

**Reproduction appendix**, short: the folder structure of this directory and the exact command for each experiment. The code does not go in the body of the dissertation, it is linked.
