# Benchmarks

Reproducible experiments backing the figures of Chapter 4 of the dissertation.
Each folder is a self-contained experiment following the same template:
`README.md` (question, environment, how to run), `measure.sh` (takes the measurements and stores the raw data), `analyze.py` (statistics from the CSV) and `results/` (raw CSVs and environment metadata).

## Index

| # | Experiment | Question | Status |
|---|---|---|---|
| 01 | [Subprocess startup](./01_subprocess_startup/) | How much of the per-source time is startup and how much is actual work? | Measured |
| 02 | [ETL latency](./02_etl_latency/) | How is end-to-end latency split across the four stages, and how did it evolve? | Pending |
| 03 | [JSONB and GIN](./03_jsonb_gin/) | What does the GIN index on `raw_articles.payload` buy, and from what volume on? | Pending |
| 04 | [API load](./04_api_load/) | From what request rate does the API degrade with a single worker? | Pending |
| 05 | [Inference resources](./05_inference_resources/) | How much CPU and memory does FinBERT use per batch, and where is the ceiling? | Pending |
| 06 | [API latency](./06_api_latency/) | How long does a request take under the load of one client, with the cache warm and cold? | Ready, not run |

## Rules

1. **Measuring and analysing are separate steps.** Raw data is always kept, so the analysis can be repeated without measuring again.
2. **Every run records its own environment:** date, repository commit, container image, cores, memory and library versions.
3. **A CSV is never edited by hand.** If a data point is wrong, measure again.
4. **Fixed seed** in anything involving randomness, such as bootstrap resampling.
5. **Fixed repetition count, 30.** The first one is reported separately because of the cache effect: the first import pays for the disk read that later ones find in the page cache.
6. **Whatever is quoted in the dissertation lives in the repository**, and the dissertation cites the exact commit. If the environment file says `dirty_tree: yes`, that commit does not identify the measured code and the run cannot be quoted.

No machine address is written into these files: the SSH target comes from
`VPS_USER` and `VPS_IP` in the root `.env`, which is not in git.

## How this maps to the dissertation

**Experimental setup**, once, at the start of Chapter 4: a 2-core server with 3.8 GB of memory, the ETL image tag, the Python and library versions, the statistical criteria, and a link to this directory at the exact commit. The actual values are copied from the environment file of the run being quoted, not from here.

Statistical criteria, written once and valid for every table: the **median** is reported instead of the mean because network retries and CPU contention produce outliers that shift the mean without being representative; dispersion is given as the interquartile range; the 95 % confidence interval of the median is estimated by **bootstrap** with 10,000 resamples and a fixed seed, following Efron and Tibshirani (1993), *An Introduction to the Bootstrap*, Chapman & Hall.

**Before each table**, a short procedure paragraph: what is measured, how, and how many repetitions. **In each table footer**, n, time window and data source.

**Reproduction appendix**, short: the folder structure of this directory and the exact command for each experiment. The code does not go in the body of the dissertation, it is linked.
