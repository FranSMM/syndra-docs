# 01 - Subprocess startup cost

**Question:** how much of the per-source time of Extract and Load is subprocess startup, and how much is actual work?

**Why it matters:** the flow spawns one subprocess per feed (`scrapy crawl` in Extract, `python -m app.scraper.load_to_db` in Load). If startup dominates, the zcost of adding a source is fixed and does not depend on the article volume.

**What is measured:** wall time of spawning each subprocess, with no network and no writes.

- `python_empty`: start the interpreter importing nothing. Baseline.
- `import_scrapy`, `import_sqlalchemy`: import the library alone. Both fall short of the real startup and are here to show the difference.
- `extraction_startup`: `scrapy list` from `/code/app/scraper`. Loads Scrapy, the project settings and the spiders without touching the network.
- `load_startup`: import `app.scraper.load_to_db` from `/code`. Pulls in SQLAlchemy, asyncpg, Pydantic and the models without opening a connection.

**Environment:** measured inside the `syndra_scheduler` container on the VPS, where the real subprocesses run. Every run writes its own environment file. The SSH target is read from `VPS_USER` and `VPS_IP` in the root `.env`.

**Run** (from WSL, with SSH access to the VPS):

    REPS=30 ./measure.sh python3 analyze.py results/startup_YYYYMMDD_HHMMSS.csv \ > results/startup_YYYYMMDD_HHMMSS_summary.csv

That is 150 process spawns on a 2-core machine, roughly 2 minutes of CPU. Do not run it while the ETL flow is running if the numbers are going to be quoted.

**Statistics:** median, interquartile range and a 95 % bootstrap confidence interval of the median (10,000 resamples, seed 2026). The first repetition is reported separately as an approximation of the cold start.

**Results:** raw CSVs, summaries and environment metadata live in `results/`.
They are never edited by hand: if something is wrong, measure again.

**Comparison:** the per-feed medians derived from `prefect_db` (ADR 041) are the reference this startup cost is contrasted against. That figure comes from warm production and is not taken here.
