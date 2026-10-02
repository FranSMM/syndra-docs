# 07 - Cost of the ML stages

**Question:** why do the two ML stages of the ETL take about the same time whether a run brings 3 articles or 60? Experiment 02 shows that tripling the feeds adds only 0.5 s to each of them.

**Hypothesis:** each run pays a fixed cost before the first article, because every stage is a fresh subprocess (`python -m app.ml.enrich_sentiment`, `python -m app.backfill_vectors`) that starts the interpreter, imports torch and transformers, and loads its model.

**What is measured:**

1. **Fixed and per-article cost, from production history.** For every ML stage run in `prefect_db`, its duration and N, the number of articles it processed. N comes from the log lines the stages write, "Processing batch of N articles" and "Encoding batch of N articles", summed when a run has several batches. Each stage then gets a straight-line fit, duration = a + b·N: a is the fixed cost per run and b the cost per article.
2. **What the fixed cost is made of, timed in the deployed image.** Inside the production scheduler, like experiment 01, each piece is timed in a fresh process, 30 times:

| Measurement | What it runs |
|---|---|
| `python_empty` | the interpreter alone |
| `import_torch_transformers` | `import torch, transformers` |
| `import_sentiment_stage` | `import app.ml.enrich_sentiment` |
| `load_sentiment_models` | the import, then `FinancialSentimentAnalyzer()` and `TickerExtractor()`, as the stage does |
| `import_vector_stage` | `import app.backfill_vectors` |
| `load_vector_model` | the import, then `get_embedding_engine()`, as the stage does |
| `..._offline` | the same loads with `HF_HUB_OFFLINE=1` |

Experiment 04 imports torch before it starts its clock, so its 0.5 to 0.9 s of model loading leave out the imports; this experiment includes them.

**Two cases the fit has to handle:**

- **N = 0 is a different regime.** Both stages load their model lazily, only when there is work, so a run with no articles never loads it. Those runs are reported apart and the fit covers N > 0 only.
- **Unknown is not zero.** The vector stage only started logging its batch line partway through April 2026, so 335 earlier runs say nothing about N. A run with neither the batch line nor the stage's "nothing to do" line has an unknown N and is excluded, not counted as N = 0.

**Why the offline variant:** production loads the models with the Hugging Face hub reachable, so every load checks over the network whether the model has changed. The same load offline skips that check, and the difference between the two is its cost. Production does not set `HF_HUB_OFFLINE`; the environment file records it.

**Run** (from WSL):

    ./measure.sh
    python3 analyze.py results/ml_YYYYMMDD_HHMMSS > results/ml_YYYYMMDD_HHMMSS_summary.csv

The probe loads FinBERT, about 850 MiB, inside the production scheduler. Each block of 30 repetitions starts only when no ETL run is active and the next one is at least 10 minutes away. The next run is read from Prefect, because the hourly interval is anchored at the last deploy and its minute moves. A session takes about half an hour, depending on the ETL waits. Nothing is written in the container: it already runs with `PYTHONDONTWRITEBYTECODE=1`.

**Statistics:**

- **Coefficients of the fit:** 95 % bootstrap intervals for a and b, resampling whole runs (10,000 resamples, seed 2026).
- **Probe measurements:** median per measurement with a bootstrap interval. The first repetition is reported apart, as in 01.
- **Each piece of the fixed cost:** a difference of medians with its bootstrap interval. Imports are `import_stage` minus `python_empty`, model loading is `load_offline` minus `import_stage`, and the hub check is `load` minus `load_offline`.
- **The rest of the fixed cost:** a minus the full load. It is what the probe cannot see: Prefect's task bookkeeping, the database queries, Qdrant's set-up and the commit.

The breakdown compares the probe with the runs of the image deployed now. Older images had other library versions.

**Limits:** the probe runs between ETL runs, on an idle machine, while a real stage follows extraction and load, with whatever they leave in the page cache. The fit is a straight line through noisy runs; the medians per range of N, also in the summary, show whether a line is a fair summary.
