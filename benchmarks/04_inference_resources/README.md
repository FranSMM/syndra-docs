# 04 - Inference resources

**Question:** how long does FinBERT take and how much memory does it use when it classifies one text at a time, as production does, compared with batches of increasing size, and where is the ceiling of the scheduler's 2.5 GiB?

**Why it matters:** the enrichment step (`app/ml/enrich_sentiment.py`) calls `analyze()` once per article, so every text is a separate forward pass. Batching is the usual way to use the two cores better, but it costs memory. The cAdvisor history gives the production peak (about 1.2 GB); this experiment gives the curve behind it.

**What is measured:** the deployed ETL image (`ghcr.io/fransmm/syndra-etl:<ETL_TAG>`, or `IMAGE=...`) with FinBERT loaded by `FinancialSentimentAnalyzer`, the same class production uses, in a container limited to two CPUs and 2.5 GiB like the scheduler. Each repetition classifies the same 64 texts:

- `production`: `analyze()` once per text, the enrichment loop as it is.
- `batched`: the whole list handed to the pipeline with `batch_size` 1, 2, 4, 8, 16, 32 and 64.

Each mode and batch size runs in a fresh process, so its peak memory (`VmHWM`) is its own and includes loading the model. `cpu_ms / wall_ms` shows how many of the two cores the inference kept busy. The network is disabled: the model weights are baked into the image.

**Texts:** 256 recent articles sampled once from production, using the text the pipeline classifies (the description, or the title when there is none). Scraped text stays in `~/.cache/syndra-bench/`, never in the repository; its SHA-256 and the median and maximum token counts go into the environment file.

**Run** (from WSL, with Docker and SSH access to the VPS):

    ./measure.sh
    python3 analyze.py results/inference_YYYYMMDD_HHMMSS.csv > results/inference_YYYYMMDD_HHMMSS_summary.csv

**Statistics:** 30 repetitions per mode and batch size, the first reported apart because it pays one-off allocations. Median time per 64 texts with a 95 % bootstrap confidence interval (10,000 resamples, seed 2026), throughput, cores kept busy, and speed-up over the `production` mode. A process that exceeds 2.5 GiB is recorded as a result in the environment file, not as a script failure.

**Limits:** the laptop's cores are not the VPS's, so absolute times do not carry over; the ratios between modes and the memory figures do, because memory depends on the model and the batch, not on the CPU. Under WSL2, CPU time reads 5 to 10 % high (checked on 30/09/2026: four GIL-bound Python threads, which cannot exceed one core, showed a ratio of 1.10), so a `cpu_cores_busy` a little above 2 means both cores saturated, not the limit being exceeded; the container's affinity was verified to be cores 0 and 1 only.
